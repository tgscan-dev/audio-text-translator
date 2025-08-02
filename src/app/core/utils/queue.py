import json

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import HTTPException

from src.app.core.config import settings

_producer: None | AIOKafkaProducer = None

_text_translation_consumer: None | AIOKafkaConsumer = None
_audio_translation_consumer: None | AIOKafkaConsumer = None
_text_packaging_consumer: None | AIOKafkaConsumer = None


async def setup_text_translation_consumer() -> None:
    """初始化文本翻译的消费者"""
    global _text_translation_consumer
    try:
        _text_translation_consumer = AIOKafkaConsumer(
            settings.KAFKA_TRANSLATION_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_TRANSLATION_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Disable auto commit
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await _text_translation_consumer.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to text translation consumer: {str(e)}")


async def setup_audio_translation_consumer() -> None:
    """初始化音频转文字的消费者"""
    global _audio_translation_consumer
    try:
        _audio_translation_consumer = AIOKafkaConsumer(
            settings.KAFKA_AUDIO_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_WHISPER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Disable auto commit
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await _audio_translation_consumer.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to audio translation consumer: {str(e)}")


async def setup_text_packaging_consumer() -> None:
    """初始化文本打包的消费者"""
    global _text_packaging_consumer
    try:
        _text_packaging_consumer = AIOKafkaConsumer(
            settings.KAFKA_PACKAGE_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_PACKAGING_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=False,  # Disable auto commit
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        )
        await _text_packaging_consumer.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to text packaging consumer: {str(e)}")


async def setup_kafka_consumers() -> None:
    """初始化所有消费者"""
    await setup_text_translation_consumer()
    await setup_audio_translation_consumer()
    await setup_text_packaging_consumer()


def get_text_translation_consumer() -> AIOKafkaConsumer:
    """获取文本翻译的消费者实例"""
    global _text_translation_consumer
    if _text_translation_consumer is None:
        raise HTTPException(status_code=500, detail="Text translation consumer is not initialized")
    return _text_translation_consumer


def get_audio_translation_consumer() -> AIOKafkaConsumer:
    """获取音频转文字的消费者实例"""
    global _audio_translation_consumer
    if _audio_translation_consumer is None:
        raise HTTPException(status_code=500, detail="Audio translation consumer is not initialized")
    return _audio_translation_consumer


def get_text_packaging_consumer() -> AIOKafkaConsumer:
    """获取文本打包的消费者实例"""
    global _text_packaging_consumer
    if _text_packaging_consumer is None:
        raise HTTPException(status_code=500, detail="Text packaging consumer is not initialized")
    return _text_packaging_consumer


async def setup_kafka_producer() -> None:
    """Create and return a Kafka producer."""
    try:
        global _producer
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS, value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        await _producer.start()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Kafka producer: {str(e)}")


def get_kafka_producer() -> AIOKafkaProducer:
    """Get the Kafka producer instance."""
    global _producer
    if _producer is None:
        raise HTTPException(status_code=500, detail="Kafka producer is not initialized")
    return _producer
