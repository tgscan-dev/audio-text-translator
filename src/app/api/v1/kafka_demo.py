# from typing import Any
# from fastapi import APIRouter, Depends
#
# from src.app.service.kafka import KafkaService
#
# router = APIRouter(prefix="/kafka", tags=["kafka"])
# kafka_service = KafkaService()
#
# @router.on_event("startup")
# async def startup_event():
#     await kafka_service.start()
#
# @router.on_event("shutdown")
# async def shutdown_event():
#     await kafka_service.stop()
#
# @router.post("/send")
# async def send_message(message: dict[str, Any]):
#     """Send a message to Kafka topic."""
#     return await kafka_service.send_message(message)
#
# @router.get("/receive")
# async def receive_messages():
#     """Receive messages from Kafka topic."""
#     return await kafka_service.get_messages()