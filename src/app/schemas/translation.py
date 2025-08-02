# src/app/schemas/translation.py

from pydantic import BaseModel

from src.app.models.translation_task import LanguageCode, TaskStatus, TaskType


class CreateTaskRequest(BaseModel):
    type: TaskType

    source_file: str | None = None  # 源文件路径 (音频文件)
    reference_text: str | None = None  # 参考文本(音频文件)

    text: str | None = None  # 纯文本内容 (仅用于文本翻译任务)

    target_languages: list[LanguageCode]  # 目标语言列表

    class Config:
        json_schema_extra = {
            "example": {
                "type": "audio",
                "source_file": "1.mp3",
                "reference_text": "This is a sample reference text for verification",
                "target_languages": ["zh-CN", "ja-JP", "ko-KR", "en-US"],  # API会自动验证这些值是否在LanguageCode枚举中
            }
        }


class QueuedTask(BaseModel):
    task_id: str  # 任务唯一标识
    type: TaskType

    source_file: str | None = None  # 源文件路径
    reference_text: str | None = None  # 参考文本

    text: str | None = None

    target_languages: list[LanguageCode]  # 目标语言列表

    @staticmethod
    def from_create_request(request: CreateTaskRequest, task_id: str) -> "QueuedTask":
        """从CreateTaskRequest创建QueuedTask"""
        return QueuedTask(
            task_id=task_id,
            type=request.type,
            source_file=request.source_file,
            text=request.text,
            reference_text=request.reference_text,
            target_languages=request.target_languages,
        )


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    stt_result: str | None = None  # 语音识别结果
    stt_accuracy: float | None = None  # 语音识别准确率
    translations: dict[LanguageCode, str] | None = None  # 翻译结果，key为目标语言代码
    error_message: str | None = None  # 错误信息

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "stt_result": "Hello, this is a transcribed text from the audio file.",
                "stt_accuracy": 0.95,
                "translations": {
                    "zh-CN": "你好，这是音频文件转录的文本。",
                    "ja-JP": "こんにちは、これは音声ファイルから転写されたテキストです。",
                    "ko-KR": "안녕하세요, 이것은 오디오 파일에서 전사된 텍스트입니다。",
                    "en-US": "Hello, this is the transcribed text from the audio file.",
                },
                "error_message": None,
            }
        }
