from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src.app.models.translation_task import TaskStatus
from src.app.schemas.translation import CreateTaskRequest, TaskResponse
from src.app.service.translation import TranslationService, get_translation_service

router = APIRouter(tags=["translations"])


@router.post("/tasks", response_model=TaskResponse, response_model_exclude_none=True)
async def create_translation_task(
    request: CreateTaskRequest,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    logger.info(f"Creating new translation task. Request: {request.model_dump()}")
    task = await service.create_task(request)
    logger.info(f"Translation task created successfully with ID: {task.task_id}")

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
    logger.debug(f"Fetching status for task ID: {task_id}")
    task = await service.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    logger.debug(f"Task {task_id} status: {task.status}")

    # 转换 translations 格式
    translations = {}
    if task.translations:
        if isinstance(task.translations, list):
            # 如果是列表格式 [{'lang': 'zh-CN', 'text': '...'}]，转换为字典格式
            for trans in task.translations:
                if isinstance(trans, dict) and "lang" in trans and "text" in trans:
                    translations[trans["lang"]] = trans["text"]
        elif isinstance(task.translations, dict):
            # 如果已经是字典格式，直接使用
            translations = task.translations

    return TaskResponse(
        task_id=task.task_id,
        status=task.status,
        stt_result=task.stt_result,
        stt_accuracy=task.stt_score,
        translations=translations,
        error_message=task.error_message if hasattr(task, "error_message") else None,
    )


@router.delete("/tasks/{task_id}", status_code=204)
async def cancel_task(
    task_id: str,
    service: Annotated[TranslationService, Depends(get_translation_service)],
):
    """Cancel a translation task

    Attempts to cancel an ongoing translation task. Returns 204 on success.
    """
    logger.info(f"Attempting to cancel task: {task_id}")
    success = await service.cancel_task(task_id)
    if not success:
        logger.warning(f"Failed to cancel task {task_id}: task not found or cannot be cancelled")
        raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
    logger.info(f"Successfully cancelled task: {task_id}")
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
    logger.debug(f"Fetching translation for task {task_id} in language: {language}")
    task = await service.get_task(task_id)
    if not task:
        logger.warning(f"Task not found when fetching translation: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        logger.warning(f"Translation not ready for task {task_id}, current status: {task.status}")
        raise HTTPException(status_code=400, detail="Translation not ready")

    if not task.translations:
        logger.warning(f"No translations found for task {task_id}")
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")

    # 处理 translations 格式
    if isinstance(task.translations, list):
        # 如果是列表格式 [{'lang': 'zh-CN', 'text': '...'}]
        logger.debug(f"Processing list format translations for task {task_id}")
        for trans in task.translations:
            if isinstance(trans, dict) and "lang" in trans and "text" in trans:
                if trans["lang"] == language:
                    logger.info(f"Found translation for language {language} in task {task_id}")
                    return {"text": trans["text"]}
        logger.warning(f"Translation for language {language} not found in list format for task {task_id}")
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
    elif isinstance(task.translations, dict):
        # 如果是字典格式 {'zh-CN': '...'}
        logger.debug(f"Processing dictionary format translations for task {task_id}")
        if language not in task.translations:
            logger.warning(f"Translation for language {language} not found in dictionary format for task {task_id}")
            raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
        logger.info(f"Found translation for language {language} in task {task_id}")
        return {"text": task.translations[language]}
    else:
        logger.error(f"Invalid translations format for task {task_id}: {type(task.translations)}")
        raise HTTPException(status_code=404, detail=f"Translation for language {language} not found")
