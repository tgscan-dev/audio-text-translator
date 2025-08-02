from sqlalchemy import JSON, Column, DateTime, Integer, String

from ..core.db.database import Base


class TranslationPackage(Base):
    __tablename__ = "translation_packages"

    id = Column(Integer, primary_key=True)
    package_id = Column(String, unique=True, index=True)
    task_id = Column(String, index=True)  # 关联的翻译任务ID

    file_path = Column(String)  # 打包文件路径
    languages = Column(JSON)  # 支持的语言列表

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
