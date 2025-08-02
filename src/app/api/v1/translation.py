from typing import Annotated

from fastapi import APIRouter, Depends

from src.app.schemas.translation import CreateTaskRequest, TaskResponse
from src.app.service.translation import TranslationService, get_translation_service
from fastapi import HTTPException

from src.app.models.translation_task import TaskStatus
router = APIRouter(tags=["translations"])


@router.post("/tasks", response_model=TaskResponse, response_model_exclude_none=True)
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





@router.get("/tasks/{task_id}", response_model=TaskResponse, response_model_exclude_none=True)
async def get_task_status(
    task_id: str,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    """Get task status
    
    Returns the current status and results of a translation task
    """
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 转换 translations 格式
    translations = {}
    if task.translations:
        if isinstance(task.translations, list):
            # 如果是列表格式 [{'lang': 'zh-CN', 'text': '...'}]，转换为字典格式
            for trans in task.translations:
                if isinstance(trans, dict) and 'lang' in trans and 'text' in trans:
                    translations[trans['lang']] = trans['text']
        elif isinstance(task.translations, dict):
            # 如果已经是字典格式，直接使用
            translations = task.translations

    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        stt_result=task.stt_result,
        stt_accuracy=task.stt_score,
        translations=translations,
        error_message=task.error_message if hasattr(task, 'error_message') else None
    )


@router.delete("/tasks/{task_id}", status_code=204)
async def cancel_task(
    task_id: str,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    """Cancel a translation task
    
    Attempts to cancel an ongoing translation task. Returns 204 on success.
    """
    success = await service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    return None


@router.get("/tasks/{task_id}/translations/{language}", response_model_exclude_none=True)
async def get_translation(
    task_id: str,
    language: str,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    """Get translation result
    
    Returns the translation result for a specific language
    """
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Translation not ready")

    if not task.translations:
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")

    # 处理 translations 格式
    if isinstance(task.translations, list):
        # 如果是列表格式 [{'lang': 'zh-CN', 'text': '...'}]
        for trans in task.translations:
            if isinstance(trans, dict) and 'lang' in trans and 'text' in trans:
                if trans['lang'] == language:
                    return {"text": trans['text']}
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
    elif isinstance(task.translations, dict):
        # 如果是字典格式 {'zh-CN': '...'}
        if language not in task.translations:
            raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
        return {"text": task.translations[language]}
    else:
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
