import asyncio

from loguru import logger
from pydantic import ValidationError

from src.app.core.utils.queue import get_text_translation_consumer, setup_text_translation_consumer
from src.app.schemas.translation import CreateTaskRequest


async def process_text_translation_messages():
    """处理文本翻译的消息"""
    consumer = get_text_translation_consumer()
    logger.info("Started text translation consumer")
    async for msg in consumer:
        try:
            logger.info(f"Received translation message: {msg.value}")

            # 反序列化消息
            try:
                task_request = CreateTaskRequest.model_validate(msg.value)
                logger.info(
                    f"Translation task request: type={task_request.type}, "
                    f"source={task_request.source_file}, "
                    f"targets={task_request.target_languages}"
                )

                # TODO: 处理文本翻译任务
                # await process_text_translation(task_request)
            except ValidationError as e:
                logger.error(f"Invalid translation message format: {str(e)}")
                # 无效消息直接提交，避免重复处理
                await consumer.commit()
                continue

            await consumer.commit()
            logger.info("Translation message processed and committed")
        except Exception as e:
            logger.error(f"Error processing translation message: {str(e)}")


async def run_worker():
    """启动文本翻译worker"""
    logger.info("Starting text translation worker")
    await setup_text_translation_consumer()
    await process_text_translation_messages()


if __name__ == "__main__":
    asyncio.run(run_worker())
