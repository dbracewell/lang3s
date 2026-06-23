from fastapi import APIRouter

from lang3s.core.logger import get_logger

logger = get_logger(__name__)

topic_router = APIRouter(
    prefix="/topics",
    tags=["topics"],
    responses={404: {"description": "Not found"}},
)
