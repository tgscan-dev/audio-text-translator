from enum import Enum

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy import Enum as SQLEnum

from ..core.db.database import Base


class TaskStatus(str, Enum):
    PENDING = "pending"  # 等待处理
    TO_PACKING = "to_packing"  # 等待打包
    COMPLETED = "completed"  # 完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskType(str, Enum):
    AUDIO = "audio"  # 音频翻译任务
    TEXT = "text"  # 纯文本翻译任务


class LanguageCode(str, Enum):
    """支持的目标语言代码"""

    ZH_CN = "zh-CN"  # 简体中文
    ZH_TW = "zh-TW"  # 繁体中文
    EN_US = "en-US"  # 英语(美国)
    JA_JP = "ja-JP"  # 日语
    KO_KR = "ko-KR"  # 韩语
    FR_FR = "fr-FR"  # 法语
    DE_DE = "de-DE"  # 德语
    ES_ES = "es-ES"  # 西班牙语
    RU_RU = "ru-RU"  # 俄语
    VI_VN = "vi-VN"  # 越南语


class TranslationTask(Base):
    __tablename__ = "translation_tasks"

    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, index=True)  # 任务唯一标识
    type = Column(SQLEnum(TaskType))  # 任务类型

    status = Column(SQLEnum(TaskStatus))  # 任务状态

    source_file = Column(String)  # 源文件路径 (音频)
    reference_text = Column(String, nullable=True)  # 参考文本(用于校验)(音频)

    text = Column(String, nullable=True)  # 纯文本内容 (文本翻译任务)

    # 任务配置
    target_languages = Column(JSON)  # 目标语言列表

    # 处理结果
    stt_result = Column(String, nullable=True)  # 语音识别结果
    stt_score = Column(JSON, nullable=True)  # 语音识别得分
    translations = Column(JSON, nullable=True)  # 各语言翻译结果
    packed_file = Column(String, nullable=True)  # 打包文件路径

    # 时间戳
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
