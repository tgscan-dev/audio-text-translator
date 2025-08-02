import asyncio
import traceback

from loguru import logger
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_none

from src.app.core.config import settings
from src.app.core.db.database import local_session
from src.app.core.utils.multilingual_translation import translate
from src.app.core.utils.message_queue import (
    get_kafka_producer,
    get_text_translation_consumer,
    setup_text_translation_consumer,
)
from src.app.models.translation_task import TaskStatus
from src.app.schemas.translation import QueuedTask
from src.app.service.translation import TranslationService


async def validate_message(msg):
    """Validate message format"""
    try:
        return QueuedTask.model_validate(msg.value)
    except ValidationError as e:
        logger.error(f"Message validation failed: {str(e)}")
        return None


async def validate_task_status(translation_service, queued_task):
    """Validate task status"""
    task = await translation_service.get_task(queued_task.task_id)

    if not task:
        logger.error(f"Task {queued_task.task_id} not found in database")
        return None

    if task.status != TaskStatus.PENDING:
        logger.warning(f"Task {queued_task.task_id} invalid status: {task.status}, expected: PENDING")
        return None

    return task


@retry(stop=stop_after_attempt(3), wait=wait_none())
async def process_translation_task(queued_task):
    """Process text translation task"""
    source_text = queued_task.text

    logger.info(
        f"🎯 Task {queued_task.task_id} - Started Processing"
        f"\n└── Type: {queued_task.type}"
        f"\n└── Source Text: {source_text[:50]}..."  # Log first 50 chars for brevity
        f"\n└── Target Languages: {queued_task.target_languages}"
    )

    # Execute translation
    start_time = asyncio.get_event_loop().time()
    translation_result = await translate(source_text, queued_task.target_languages)
    translation_time = asyncio.get_event_loop().time() - start_time

    # Log translation results
    logger.info(
        f"🎉 Task {queued_task.task_id} - Translation Completed in {translation_time:.2f}s"
        f"\n└── Target Languages: {[t.lang for t in translation_result.translations]}"
    )

    return translation_result


async def update_task_result(translation_service, task, translation_result):
    """Update task result"""
    task.translations = [t.model_dump() for t in translation_result.translations]
    task.status = TaskStatus.TO_PACKING

    await translation_service.update_task(task)


@retry(stop=stop_after_attempt(3), wait=wait_none())
async def process_single_message(consumer, translation_service, msg):
    """Process single message"""
    queued_task = None
    # await consumer.commit() #debug

    try:
        # Validate message format
        queued_task = await validate_message(msg)
        if not queued_task:
            await consumer.commit()
            return

        # Validate task status
        task = await validate_task_status(translation_service, queued_task)
        if not task:
            await consumer.commit()
            return

        # Process translation task
        translation_result = await process_translation_task(queued_task)

        # Update task result
        await update_task_result(translation_service, task, translation_result)

        producer = await get_kafka_producer()
        logger.debug(f"Sending task {queued_task.task_id} to package topic")
        await producer.send(settings.KAFKA_PACKAGE_TOPIC, queued_task.model_dump())

        await consumer.commit()
        logger.debug(f"Task {queued_task.task_id} message processed and committed")

    except Exception as e:
        task_id = queued_task.task_id if queued_task else "unknown"
        error_trace = traceback.format_exc()
        logger.error(f"Task {task_id} processing failed: {str(e)}\n{error_trace}")

        # Rollback database transaction
        await translation_service.db.rollback()


async def process_text_messages():
    """Process text translation messages"""
    consumer = get_text_translation_consumer()
    logger.info("🚀 Text Translation Service Started")

    # Create database session and service
    db = local_session()
    translation_service = TranslationService(db)

    try:
        logger.info("📥 Waiting for incoming text translation tasks...")
        async for msg in consumer:
            await process_single_message(consumer, translation_service, msg)
    except Exception as e:
        logger.error(f"❌ Fatal error in message processing: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        # Ensure database session is closed on exit
        await db.close()
        logger.warning("🛑 Text Translation Service Stopped")


async def run_worker():
    """Start text translation worker"""
    logger.info("🔄 Initializing Text Translation Worker...")
    try:
        await setup_text_translation_consumer()
        await process_text_messages()
    except Exception as e:
        logger.error(f"💥 Worker initialization failed: {str(e)}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    asyncio.run(run_worker())
