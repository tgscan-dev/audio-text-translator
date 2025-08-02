import asyncio
import json
import traceback

from loguru import logger
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_none

from src.app.core.config import settings
from src.app.core.db.database import local_session
from src.app.core.utils.message_queue import (
    get_audio_translation_consumer,
    get_kafka_producer,
    setup_audio_translation_consumer,
)
from src.app.core.utils.multilingual_translation import translate
from src.app.core.utils.stt import aspeech2text
from src.app.core.utils.stt_score import validate_stt
from src.app.models.translation_task import TaskStatus
from src.app.schemas.translation import QueuedTask
from src.app.service.translation import TranslationService


async def validate_message(msg):
    """验证消息格式"""
    try:
        return QueuedTask.model_validate(msg.value)
    except ValidationError as e:
        logger.error(f"Message validation failed: {str(e)}")
        return None


async def validate_task_status(translation_service, queued_task):
    """验证任务状态"""
    task = await translation_service.get_task(queued_task.task_id)

    if not task:
        logger.error(f"Task {queued_task.task_id} not found in database")
        return None

    if task.status != TaskStatus.PENDING:
        logger.warning(f"Task {queued_task.task_id} invalid status: {task.status}, expected: PENDING")
        return None

    return task


@retry(stop=stop_after_attempt(3), wait=wait_none())
async def process_audio_task(queued_task):
    """处理音频转文字任务"""
    source_file = queued_task.source_file

    logger.info(
        f"🎯 Task {queued_task.task_id} - Started Processing"
        f"\n└── Type: {queued_task.type}"
        f"\n└── Source: {source_file}"
        f"\n└── Target Languages: {queued_task.target_languages}"
    )

    # 执行语音转文字
    start_time = asyncio.get_event_loop().time()
    text = await aspeech2text(source_file)
    stt_time = asyncio.get_event_loop().time() - start_time

    # 截断长文本用于日志显示
    display_text = text[:100] + "..." if len(text) > 100 else text
    logger.info(
        f"✨ Task {queued_task.task_id} - STT Completed in {stt_time:.2f}s" f"\n└── Text Preview: {display_text}"
    )

    # 并发执行打分和翻译任务
    logger.debug(f"Task {queued_task.task_id} - Starting parallel scoring and translation")
    parallel_start = asyncio.get_event_loop().time()

    score_task = validate_stt(text, queued_task.reference_text)
    translation_task = translate(text, queued_task.target_languages)
    score, translation_result = await asyncio.gather(score_task, translation_task)

    parallel_time = asyncio.get_event_loop().time() - parallel_start

    # 记录关键结果
    logger.info(
        f"🎉 Task {queued_task.task_id} - All Processing Completed in {parallel_time:.2f}s"
        f"\n└── Score: {score.total_score:.2f}"
        f"\n└── Target Languages: {[t.lang for t in translation_result.translations]}"
    )

    # 详细分数记录在 DEBUG 级别
    logger.debug(
        f"Task {queued_task.task_id} - Detailed Score:"
        f"\n{json.dumps(score.model_dump(), indent=2, ensure_ascii=False)}"
    )

    return text, score, translation_result


async def update_task_result(translation_service, task, text, score, translation_result=None):
    """更新任务结果"""
    task.stt_result = text
    task.stt_score = score.model_dump()

    if translation_result:
        task.translations = [t.model_dump() for t in translation_result.translations]

    task.status = TaskStatus.TO_PACKING

    await translation_service.update_task(task)


@retry(stop=stop_after_attempt(3), wait=wait_none())
async def process_single_message(consumer, translation_service, msg):
    """处理单条消息"""
    queued_task = None

    try:
        # 验证消息格式
        queued_task = await validate_message(msg)
        if not queued_task:
            await consumer.commit()
            return

        # 验证任务状态
        task = await validate_task_status(translation_service, queued_task)
        if not task:
            await consumer.commit()
            return

        # 处理音频任务并并发执行打分和翻译
        text, score, translation_result = await process_audio_task(queued_task)

        # 记录翻译结果
        logger.info(
            f"Task {queued_task.task_id} translation completed - "
            f"target languages: {[t.lang for t in translation_result.translations]}"
        )

        # 更新任务结果
        await update_task_result(translation_service, task, text, score, translation_result)

        producer = await get_kafka_producer()
        logger.debug(f"Sending task {queued_task.task_id} to package topic")
        await producer.send(settings.KAFKA_PACKAGE_TOPIC, queued_task.model_dump())

        await consumer.commit()
        logger.debug(f"Task {queued_task.task_id} message processed and committed")

    except Exception as e:
        task_id = queued_task.task_id if queued_task else "unknown"
        error_trace = traceback.format_exc()
        logger.error(f"Task {task_id} processing failed: {str(e)}\n{error_trace}")

        # 回滚数据库事务
        await translation_service.db.rollback()


async def process_audio_messages():
    """处理音频转文字的消息"""
    consumer = get_audio_translation_consumer()
    logger.info("🚀 Audio Translation Service Started")

    # 创建数据库会话和服务
    db = local_session()
    translation_service = TranslationService(db)

    try:
        logger.info("📥 Waiting for incoming audio translation tasks...")
        async for msg in consumer:
            await process_single_message(consumer, translation_service, msg)
    except Exception as e:
        logger.error(f"❌ Fatal error in message processing: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        # 确保在退出时关闭数据库会话
        await db.close()
        logger.warning("🛑 Audio Translation Service Stopped")


async def run_worker():
    """启动音频处理worker"""
    logger.info("🔄 Initializing Audio Translation Worker...")
    try:
        await setup_audio_translation_consumer()
        await process_audio_messages()
    except Exception as e:
        logger.error(f"💥 Worker initialization failed: {str(e)}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    asyncio.run(run_worker())
