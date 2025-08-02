# from typing import Any
# import json
# from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
# from fastapi import HTTPException
#
# from src.app.core.config import settings
#
#
# class KafkaService:
#     def __init__(self):
#         self.producer = None
#         self.consumer = None
#         self.topic = settings.KAFKA_TOPIC
#         self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
#         self.group_id = settings.KAFKA_GROUP_ID
#
#     async def start_producer(self) -> None:
#         """Start the Kafka producer."""
#         try:
#             self.producer = AIOKafkaProducer(
#                 bootstrap_servers=self.bootstrap_servers
#             )
#             await self.producer.start()
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to connect to Kafka producer: {str(e)}")
#
#     async def start_consumer(self) -> None:
#         """Start the Kafka consumer."""
#         try:
#             self.consumer = AIOKafkaConsumer(
#                 self.topic,
#                 bootstrap_servers=self.bootstrap_servers,
#                 group_id=self.group_id,
#                 auto_offset_reset="earliest"
#             )
#             await self.consumer.start()
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to connect to Kafka consumer: {str(e)}")
#
#     async def start(self) -> None:
#         """Start both Kafka producer and consumer."""
#         await self.start_producer()
#         await self.start_consumer()
#
#     async def stop(self) -> None:
#         """Stop the Kafka producer and consumer."""
#         if self.producer:
#             await self.producer.stop()
#         if self.consumer:
#             await self.consumer.stop()
#
#     async def send_message(self, message: Any) -> dict:
#         """Send a message to Kafka topic."""
#         try:
#             value = json.dumps(message).encode()
#             await self.producer.send_and_wait(self.topic, value)
#             return {"status": "success", "message": "Message sent successfully"}
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
#
#     async def get_messages(self, timeout_ms: int = 1000) -> list:
#         """Get messages from Kafka topic."""
#         try:
#             messages = []
#             async for msg in self.consumer:
#                 try:
#                     value = json.loads(msg.value.decode())
#                     print(value)
#                     messages.append(value)
#                 except json.JSONDecodeError:
#                     messages.append(msg.value.decode())
#
#                 # Break after timeout
#                 if len(messages) >= 10:  # Limit to 10 messages
#                     break
#             return messages
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to receive messages: {str(e)}")
