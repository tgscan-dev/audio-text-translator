"""
多语言翻译文件打包模块

设计目标：
1. 空间效率 - 使用二进制格式和压缩算法
2. 查询速度 - 使用索引实现直接访问，通过mmap提升随机访问性能
3. 内存效率 - 支持部分加载，避免一次性加载全部数据
4. 灵活性 - 支持多语言和多种文本来源

文件格式设计：
[文件头(16字节)] [任务数据块1] [任务数据块2] ... [索引区]
"""

import asyncio
import mmap
import struct
import zlib
from enum import Enum
from pathlib import Path

import aiofiles

from src.app.models.translation_task import LanguageCode


class TextSource(str, Enum):
    """文本来源类型"""

    TEXT = "TEXT"  # 原始文本输入
    AUDIO = "AUDIO"  # 语音识别得到的文本


class PackageHeader:
    """文件头结构
    总大小：16字节
    组成部分：
    - 魔数 (4字节)：固定值'MLTR'，用于识别文件类型
    - 版本号 (1字节)：当前版本为1
    - 索引区偏移量 (8字节)：指向文件中索引区的开始位置
    """

    MAGIC = b"MLTR"  # 文件类型标识
    VERSION = 1  # 当前版本号
    FORMAT = "!4sBI"  # 打包格式：魔数(4s) + 版本号(B) + 索引偏移量(I)
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, index_offset: int):
        self.index_offset = index_offset

    def pack(self) -> bytes:
        """将文件头打包为字节串"""
        return struct.pack(self.FORMAT, self.MAGIC, self.VERSION, self.index_offset)

    @classmethod
    def unpack(cls, data: bytes) -> "PackageHeader":
        """从字节串解包文件头"""
        magic, version, index_offset = struct.unpack(cls.FORMAT, data)
        if magic != cls.MAGIC:
            raise ValueError("无效的文件格式")
        if version != cls.VERSION:
            raise ValueError(f"不支持的版本号: {version}")
        return cls(index_offset)


class IndexEntry:
    """索引项结构
    总大小：48字节
    组成部分：
    - 任务ID (36字节)：UUID字符串
    - 数据大小 (4字节)：uint32
    - 数据偏移量 (8字节)：uint64，指向任务数据在文件中的位置
    """

    FORMAT = "!36sIQ"  # 打包格式：任务ID(36s) + 数据大小(I) + 偏移量(Q)
    SIZE = struct.calcsize(FORMAT)

    def __init__(self, task_id: str, offset: int, size: int):
        self.task_id = task_id  # 任务唯一标识
        self.offset = offset  # 数据在文件中的位置
        self.size = size  # 数据块大小

    def pack(self) -> bytes:
        """将索引项打包为字节串"""
        return struct.pack(self.FORMAT, self.task_id.encode(), self.size, self.offset)

    @classmethod
    def unpack(cls, data: bytes) -> "IndexEntry":
        """从字节串解包索引项"""
        task_id, size, offset = struct.unpack(cls.FORMAT, data)
        return cls(task_id.decode().strip("\x00"), offset, size)


class TaskData:
    """任务数据结构
    存储一个任务的所有翻译结果，包括：
    - 不同语言的翻译
    - 不同来源(TEXT/AUDIO)的文本
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        # 二层字典：来源 -> 语言 -> 文本
        self.translations: dict[TextSource, dict[LanguageCode, str]] = {
            TextSource.TEXT: {},  # 原始文本的翻译
            TextSource.AUDIO: {},  # 语音识别文本的翻译
        }

    def add_translation(self, source: TextSource, language: LanguageCode, text: str):
        """添加一条翻译"""
        self.translations[source][language] = text

    def get_translation(self, source: TextSource, language: LanguageCode) -> str | None:
        """获取指定来源和语言的翻译"""
        return self.translations[source].get(language)

    def pack(self) -> bytes:
        """将任务数据压缩打包为字节串"""
        data = {
            "task_id": self.task_id,
            "translations": {
                source.value: {lang.value: text for lang, text in translations.items()}
                for source, translations in self.translations.items()
            },
        }
        return zlib.compress(str(data).encode(), level=9)

    @classmethod
    def unpack(cls, data: bytes) -> "TaskData":
        """从压缩的字节串解包任务数据"""
        decompressed = eval(zlib.decompress(data).decode())
        task = cls(decompressed["task_id"])
        for source_str, translations in decompressed["translations"].items():
            source = TextSource(source_str)
            for lang_str, text in translations.items():
                task.add_translation(source, LanguageCode(lang_str), text)
        return task


class TranslationPackage:
    """翻译包文件管理类

    使用异步IO和mmap进行文件访问优化：
    1. 异步文件操作，避免阻塞
    2. 文件映射到内存，提供更快的随机访问
    3. 系统级的缓存机制
    4. 避免频繁的文件IO操作
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.index: dict[str, IndexEntry] = {}
        self._mmap: mmap.mmap | None = None
        self._file = None
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def open(self):
        """异步打开文件并创建内存映射"""
        async with self._lock:
            if self._mmap is None:
                # 使用同步操作创建mmap，因为mmap操作是系统调用，不会阻塞IO
                self._file = open(self.file_path, "rb")
                self._mmap = mmap.mmap(
                    self._file.fileno(),
                    0,  # 0表示映射整个文件
                    access=mmap.ACCESS_READ,  # 只读模式
                )
                await self.load_index()  # 异步加载索引

    async def close(self):
        """异步关闭内存映射和文件"""
        async with self._lock:
            if self._mmap is not None:
                self._mmap.close()
                self._mmap = None
            if self._file is not None:
                self._file.close()
                self._file = None

    async def create(self, tasks: list[TaskData]):
        """异步创建新的翻译包文件"""
        async with aiofiles.open(self.file_path, "wb") as f:
            # 写入临时文件头
            await f.write(PackageHeader(0).pack())

            # 写入任务数据并构建索引
            for task in tasks:
                data = task.pack()
                current_pos = await f.tell()
                self.index[task.task_id] = IndexEntry(task_id=task.task_id, offset=current_pos, size=len(data))
                await f.write(data)

            # 写入索引区
            index_offset = await f.tell()
            for entry in self.index.values():
                await f.write(entry.pack())

            # 更新文件头
            await f.seek(0)
            await f.write(PackageHeader(index_offset).pack())

    async def load_index(self):
        """异步加载文件索引
        使用mmap进行快速读取
        """
        # 读取文件头
        header = PackageHeader.unpack(self._mmap[: PackageHeader.SIZE])

        # 读取索引区
        index_data = self._mmap[header.index_offset :]
        pos = 0
        while pos < len(index_data):
            entry_data = index_data[pos : pos + IndexEntry.SIZE]
            if len(entry_data) < IndexEntry.SIZE:
                break
            entry = IndexEntry.unpack(entry_data)
            self.index[entry.task_id] = entry
            pos += IndexEntry.SIZE

    async def get_task(self, task_id: str) -> TaskData | None:
        """异步获取指定任务的数据
        使用mmap进行快速随机访问
        """
        if task_id not in self.index:
            return None

        entry = self.index[task_id]
        data = self._mmap[entry.offset : entry.offset + entry.size]
        return TaskData.unpack(data)

    async def query_text(self, language: LanguageCode, task_id: str, source: TextSource) -> str | None:
        """异步查询特定的翻译文本
        实现"语言 -> 文本编号 -> 文本来源"的查询
        """
        if self._mmap is None:
            await self.open()

        task = await self.get_task(task_id)
        if not task:
            return None
        return task.get_translation(source, language)


async def create_package_example():
    """创建示例翻译包文件并演示异步mmap访问"""
    # 创建示例任务数据
    task = TaskData("task-123")
    task.add_translation(TextSource.TEXT, LanguageCode.ZH_CN, "你好世界")
    task.add_translation(TextSource.TEXT, LanguageCode.EN_US, "Hello World")
    task.add_translation(TextSource.AUDIO, LanguageCode.ZH_CN, "语音识别的文本")
    task.add_translation(TextSource.AUDIO, LanguageCode.EN_US, "Speech recognized text")

    # 创建翻译包文件
    package = TranslationPackage("translations.bin")
    await package.create([task])

    # 使用异步上下文管理器访问文件
    async with TranslationPackage("translations.bin") as package:
        # 异步查询示例
        text = await package.query_text(LanguageCode.ZH_CN, "task-123", TextSource.TEXT)
        print(f"查询结果: {text}")  # 输出: 你好世界

        # 并发查询示例
        text2 = await package.query_text(LanguageCode.EN_US, "task-123", TextSource.AUDIO)
        print(f"查询结果2: {text2}")  # 输出: Speech recognized text


if __name__ == "__main__":
    asyncio.run(create_package_example())
