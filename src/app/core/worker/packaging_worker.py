import asyncio

from loguru import logger

from src.app.core.utils.queue import get_text_packaging_consumer, setup_text_packaging_consumer


async def process_text_packaging_messages():
    """处理文本打包的消息"""
    consumer = get_text_packaging_consumer()
    logger.info("Started text packaging consumer")
    async for msg in consumer:
        try:
            logger.info(f"Received packaging message: {msg.value}")
            # TODO: 处理文本打包任务
            # await process_text_packaging(msg.value)

            await consumer.commit()
            logger.info("Packaging message processed and committed")
        except Exception as e:
            logger.error(f"Error processing packaging message: {str(e)}")


async def run_worker():
    """启动文本打包worker"""
    logger.info("Starting text packaging worker")
    await setup_text_packaging_consumer()
    await process_text_packaging_messages()


if __name__ == "__main__":
    asyncio.run(run_worker())
