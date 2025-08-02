import asyncio
import traceback
from datetime import datetime, UTC
from pathlib import Path
import psutil

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_none

from src.app.core.config import settings
from src.app.core.db.database import local_session
from src.app.core.utils.package_file import TaskData, TextSource, TranslationPackage
from src.app.core.utils.message_queue import get_text_packaging_consumer, setup_text_packaging_consumer
from src.app.models.translation_task import LanguageCode, TaskStatus
from src.app.schemas.translation import QueuedTask
from src.app.service.translation import TranslationService


async def validate_message(msg):
    """Validate message format"""
    try:
        return QueuedTask.model_validate(msg.value)
    except Exception as e:
        logger.error(f"Message validation failed: {str(e)}")
        return None


async def validate_task_status(translation_service, queued_task):
    """Validate task status"""
    task = await translation_service.get_task(queued_task.task_id)

    if not task:
        logger.error(f"Task {queued_task.task_id} not found in database")
        return None

    if task.status != TaskStatus.TO_PACKING:
        logger.warning(f"Task {queued_task.task_id} invalid status: {task.status}, expected: TO_PACKING")
        return None

    return task


@retry(stop=stop_after_attempt(3), wait=wait_none())
async def process_package_task(task):
    """Process package task"""
    logger.info(
        f"🎯 Task {task.task_id} - Started Packaging"
        f"\n└── Type: {task.type}"
        f"\n└── Target Languages: {task.target_languages}"
    )

    # Create package data
    package_data = TaskData(task.task_id)

    # Add text translations
    for translation in task.translations:
        lang = LanguageCode(translation["lang"])
        text = translation["text"]
        package_data.add_translation(TextSource.TEXT, lang, text)

    # Add audio translations if available
    if task.stt_result:
        for lang in task.target_languages:
            package_data.add_translation(TextSource.AUDIO, LanguageCode(lang), task.stt_result)

    # Create package file
    package_dir = Path(settings.PACKAGE_DIR)
    if not package_dir.is_absolute():
        # 如果不是绝对路径，则从项目根目录开始
        project_root = Path(__file__).parent.parent.parent.parent.parent
        package_dir = project_root / settings.PACKAGE_DIR

    # 确保目录存在
    package_dir.mkdir(parents=True, exist_ok=True)

    package_file = package_dir / f"{task.task_id}.bin"
    package = TranslationPackage(package_file)
    await package.create([package_data])

    return str(package_file)


async def update_task_result(translation_service, task, package_file):
    """Update task result"""
    task.packed_file = package_file
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now()

    await translation_service.update_task(task)



async def process_single_message(msg):
    """Process a single message and return its offset if successful"""
    db = local_session()
    translation_service = TranslationService(db)
    
    try:
        queued_task = await validate_message(msg)
        if not queued_task:
            return None

        task = await validate_task_status(translation_service, queued_task)
        if not task:
            return None

        package_file = await process_package_task(task)
        await update_task_result(translation_service, task, package_file)
        return msg.offset
            
    except Exception as e:
        task_id = queued_task.task_id if queued_task else "unknown"
        error_trace = traceback.format_exc()
        logger.error(f"Task {task_id} processing failed: {str(e)}\n{error_trace}")
        await translation_service.db.rollback()
        return None
    finally:
        await db.close()

async def process_partition_messages(consumer, partition, messages):
    """Process messages from a single partition concurrently"""
    # 创建所有消息的并发任务
    tasks = [
        asyncio.create_task(process_single_message(msg))
        for msg in messages
    ]
    
    # 等待所有任务完成
    done = await asyncio.gather(*tasks)
    
    # 收集成功处理的消息 offset
    offsets = [offset for offset in done if offset is not None]
    
    # 提交该分区的最大 offset + 1
    if offsets:
        max_offset = max(offsets)
        await consumer.commit({
            partition: max_offset + 1
        })
        logger.debug(f"Partition {partition.topic}[{partition.partition}] processed and committed up to offset {max_offset}")

def get_dynamic_batch_size():
    """根据内存使用情况动态调整批处理大小"""
    # 获取内存使用情况
    memory = psutil.virtual_memory()
    
    # 基础批处理大小
    BASE_BATCH_SIZE = 50
    
    # 根据可用内存百分比调整批处理大小
    if memory.percent >= 90:  # 内存使用率 >= 90%
        return max(10, BASE_BATCH_SIZE // 4)  # 最小保持10
    elif memory.percent >= 80:  # 内存使用率 >= 80%
        return BASE_BATCH_SIZE // 2  # 25
    elif memory.percent >= 70:  # 内存使用率 >= 70%
        return BASE_BATCH_SIZE  # 50
    else:  # 内存充足
        return min(BASE_BATCH_SIZE * 2, 200)  # 最大不超过200

async def process_package_messages():
    """Process package messages concurrently"""
    consumer = get_text_packaging_consumer()
    logger.info("🚀 Package Service Started")

    # 初始批处理大小
    batch_size = get_dynamic_batch_size()
    last_memory_check = datetime.now()
    MEMORY_CHECK_INTERVAL = 60  # 每60秒检查一次内存使用情况

    try:
        logger.info("📥 Waiting for incoming package tasks...")
        while True:
            # 检查是否需要更新批处理大小
            now = datetime.now()
            if (now - last_memory_check).seconds >= MEMORY_CHECK_INTERVAL:
                new_batch_size = get_dynamic_batch_size()
                if new_batch_size != batch_size:
                    logger.info(f"Adjusting batch size from {batch_size} to {new_batch_size} based on memory usage")
                    batch_size = new_batch_size
                last_memory_check = now

            # 使用 getmany 批量获取消息
            messages = await consumer.getmany(timeout_ms=1000, max_records=batch_size)
            
            if not messages:
                # 如果没有新消息，短暂等待后继续
                await asyncio.sleep(0.1)
                continue
                
            # 处理每个分区的消息
            for partition, partition_messages in messages.items():
                if not partition_messages:
                    continue
                    
                await process_partition_messages(
                    consumer, 
                    partition, 
                    partition_messages, 
                )

    except Exception as e:
        logger.error(f"❌ Fatal error in message processing: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        logger.warning("🛑 Package Service Stopped")


async def run_worker():
    """Start package worker"""
    logger.info("🔄 Initializing Package Worker...")
    try:
        await setup_text_packaging_consumer()
        await process_package_messages()
    except Exception as e:
        logger.error(f"💥 Worker initialization failed: {str(e)}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    asyncio.run(run_worker())
