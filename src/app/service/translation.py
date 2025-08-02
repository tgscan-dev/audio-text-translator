import uuid
from datetime import datetime

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import settings
from src.app.core.db.database import async_get_db
from src.app.core.utils.queue import get_kafka_producer
from src.app.models.translation_task import TaskStatus, TaskType, TranslationTask
from src.app.schemas.translation import CreateTaskRequest


class TranslationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_task(self, task_id: str) -> TranslationTask | None:
        """获取任务信息"""
        query = select(TranslationTask).where(TranslationTask.task_id == task_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = await self.get_task(task_id)
        if not task or task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        task.status = TaskStatus.CANCELLED
        await self.db.commit()
        return True

    async def create_task(self, request: CreateTaskRequest) -> TranslationTask:
        """创建新的翻译任务"""
        # 创建任务实例
        task = TranslationTask()
        task.task_id = str(uuid.uuid4())
        task.type = request.type
        task.source_file = request.source_file
        task.reference_text = request.reference_text
        task.target_languages = request.target_languages
        task.status = TaskStatus.PENDING
        task.created_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        # 添加到数据库
        self.db.add(task)

        # 发送到消息队列
        producer = get_kafka_producer()
        request_dict = request.model_dump()
        if request.type == TaskType.TEXT:
            await producer.send(settings.KAFKA_TRANSLATION_TOPIC, request_dict)  # 发送文本翻译任务
        elif request.type == TaskType.AUDIO:
            await producer.send(settings.KAFKA_AUDIO_TOPIC, request_dict)  # 发送音频翻译任务

        await self.db.commit()
        await self.db.refresh(task)

        return task


async def get_translation_service(db: AsyncSession = Depends(async_get_db)) -> TranslationService:
    """依赖注入函数，用于获取TranslationService实例"""
    return TranslationService(db)
