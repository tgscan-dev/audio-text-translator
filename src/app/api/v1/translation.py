from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.schemas.translation import CreateTaskRequest, TaskResponse
from src.app.service.translation import TranslationService, get_translation_service

router = APIRouter(tags=["translations"])


@router.post("/tasks", response_model=TaskResponse)
async def create_translation_task(
    request: CreateTaskRequest,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    task = await service.create_task(request)

    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        stt_result=task.stt_result,
        stt_accuracy=task.stt_score,
        translations=task.translations,
        error_message=None,
    )


#
#
# @router.get("/tasks/{task_id}", response_model=TaskResponse)
# async def get_task_status(
#     task_id: str,
#     service: Annotated[TranslationService, Depends(get_translation_service)],
# ):
#     """获取任务状态"""
#     task = await service.get_task(task_id)
#     if not task:
#         raise HTTPException(status_code=404, detail="Task not found")
#
#     return TaskResponse(
#         task_id=task.task_id,
#         status=task.status,
#         progress=None,  # TODO: 实现进度追踪
#         stt_result=task.stt_result,
#         stt_accuracy=task.stt_accuracy,
#         translations=task.translations,
#         error_message=None
#     )
#
#
# @router.delete("/tasks/{task_id}")
# async def cancel_task(
#     task_id: str,
#     service: Annotated[TranslationService, Depends(get_translation_service)],
# ):
#     """取消任务"""
#     success = await service.cancel_task(task_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
#
#
# @router.get("/packages/{task_id}/text")
# async def query_translation(
#     task_id: str,
#     language: str,
#     service: Annotated[TranslationService, Depends(get_translation_service)],
# ):
#     """查询翻译文本"""
#     task = await service.get_task(task_id)
#     if not task:
#         raise HTTPException(status_code=404, detail="Task not found")
#
#     if task.status != TaskStatus.COMPLETED:
#         raise HTTPException(status_code=400, detail="Translation not ready")
#
#     if not task.translations or language not in task.translations:
#         raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
#
#     return {"text": task.translations[language]}
