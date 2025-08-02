from fastapi import APIRouter

from .translation import router as translation_router

# from .kafka_demo import router as kafka_router

router = APIRouter(prefix="/v1")
router.include_router(translation_router)
# router.include_router(kafka_router)
