import asyncio

from loguru import logger
from pydantic import ValidationError

from src.app.core.utils.queue import get_audio_translation_consumer, setup_audio_translation_consumer
from src.app.schemas.translation import CreateTaskRequest


async def process_audio_messages():
    """处理音频转文字的消息"""
    consumer = get_audio_translation_consumer()
    logger.info("Started audio translation consumer")
    async for msg in consumer:
        try:
            logger.info(f"Received audio message: {msg.value}")

            # 反序列化消息
            try:
                task_request = CreateTaskRequest.model_validate(msg.value)
                logger.info(
                    f"Audio task request: type={task_request.type}, "
                    f"source={task_request.source_file}, "
                    f"targets={task_request.target_languages}"
                )

                # TODO: 处理音频转文字任务
                # await process_audio_translation(task_request)
            except ValidationError as e:
                logger.error(f"Invalid audio message format: {str(e)}")
                # 无效消息直接提交，避免重复处理
                await consumer.commit()
                continue

            await consumer.commit()
            logger.info("Audio message processed and committed")
        except Exception as e:
            logger.error(f"Error processing audio message: {str(e)}")


async def run_worker():
    """启动音频处理worker"""
    logger.info("Starting audio translation worker")
    await setup_audio_translation_consumer()
    await process_audio_messages()


if __name__ == "__main__":
    asyncio.run(run_worker())
