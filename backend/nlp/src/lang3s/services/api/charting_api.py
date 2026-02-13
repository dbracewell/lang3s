from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from lang3s.data.db.analytics_db import init_analytics_db, shutdown_analytics_db
from lang3s.services.model.charting_models import *
from lang3s.services.service.charting_service import (
    ChartingService,
    get_charting_service,
    init_charting_service,
    shutdown_charting_service,
)
from lang3s.utils.logger.service_logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/charts",
    tags=["charts"],
    responses={404: {"description": "Not found"}},
)


@asynccontextmanager
async def charting_lifecycle(app: FastAPI):
    logger.info("Initializing Charting Service...")
    init_analytics_db()
    init_charting_service()
    yield
    shutdown_analytics_db()
    shutdown_charting_service()


@router.post("", response_model=ChartResult)
async def chart_data(
    request: ChartDataRequest,
    service: ChartingService = Depends(get_charting_service),
):
    return service.get_chart_data(request)
