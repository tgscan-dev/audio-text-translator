import asyncio
from typing import Literal

from loguru import logger

from src.app.core.utils.queue import (
    setup_text_translation_consumer,
    setup_audio_translation_consumer,
    setup_text_packaging_consumer
)
from src.app.core.worker.audio_worker import process_audio_messages
from src.app.core.worker.packaging_worker import process_text_packaging_messages
from src.app.core.worker.translation_worker import process_text_translation_messages

WorkerType = Literal["all", "audio", "translation", "packaging"]


async def run_workers(worker_type: WorkerType = "all"):
    """启动指定类型的worker

    Args:
        worker_type: 要启动的worker类型
            - "all": 启动所有worker
            - "audio": 只启动音频处理worker
            - "translation": 只启动文本翻译worker
            - "packaging": 只启动文本打包worker
    """
    logger.info(f"Starting workers: {worker_type}")
    tasks = []

    # 根据类型初始化消费者并创建任务
    if worker_type in ["all", "audio"]:
        await setup_audio_translation_consumer()
        tasks.append(asyncio.create_task(process_audio_messages()))
    if worker_type in ["all", "translation"]:
        await setup_text_translation_consumer()
        tasks.append(asyncio.create_task(process_text_translation_messages()))
    if worker_type in ["all", "packaging"]:
        await setup_text_packaging_consumer()
        tasks.append(asyncio.create_task(process_text_packaging_messages()))

    try:
        # 等待所有任务完成（或者出错）
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error in worker tasks: {str(e)}")
    finally:
        # 取消所有任务
        for task in tasks:
            if not task.done():
                task.cancel()

        # 等待任务取消完成
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    import sys

    # 从命令行参数获取要启动的worker类型
    worker_type: WorkerType = "all"
    if len(sys.argv) > 1 and sys.argv[1] in ["all", "audio", "translation", "packaging"]:
        worker_type = sys.argv[1]  # type: ignore

    asyncio.run(run_workers(worker_type))
