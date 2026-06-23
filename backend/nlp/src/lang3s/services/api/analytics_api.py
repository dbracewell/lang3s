import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from lang3s.data.db.analytics_db import init_analytics_db, shutdown_analytics_db
from lang3s.services.model.analytics_models import *
from lang3s.services.service.analytics_service import (
    AnalyticsService,
    get_analytics_service,
    init_analytics_service,
    shutdown_analytics_service,
)
from lang3s.services.worker.analytics_worker import analytics_worker
from lang3s.utils.logger.service_logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

BATCH_TIMEOUT = 30

background_tasks = set()


@asynccontextmanager
async def analytics_lifecycle(app: FastAPI):
    logger.info("Initializing Analytics Service...")
    init_analytics_db()
    init_analytics_service()
    worker_task = asyncio.create_task(asyncio.to_thread(analytics_worker, app.state))
    background_tasks.add(worker_task)
    worker_task.add_done_callback(background_tasks.discard)
    yield

    app.should_exit = True
    try:
        await asyncio.wait_for(worker_task, timeout=5.0)
        logger.info("✅ Worker finished gracefully.")
    except asyncio.TimeoutError:
        pass

    logger.info("Shutting down Analytics Service...")
    shutdown_analytics_db()
    shutdown_analytics_service()


@router.get("/topic/{id}")
async def get_topic(
    id: str, service: AnalyticsService = Depends(get_analytics_service)
):
    return service.get_ranked_entities_for_topic(id)


@router.post("/cohortinformation")
async def cohort_information(
    request: AnnotationCohortInformationRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_cohort_information(request)


@router.post("/cohorts")
async def cohorts(
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_cohorts()


@router.post("/topicscore")
async def topic_score(
    request: AnnotationMetricRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_topic_score_metrics(request)


@router.post("/affinity")
async def loaners(
    request: AnnotationMetricRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_affinity_metrics(request)


@router.post("/counts")
async def counts(
    request: AnnotationCountsRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    print(request)
    return service.get_annotation_counts(request)


@router.post("/cooccurrence")
async def co_occurrence(
    request: AnnotationCoOccurrenceRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_co_occurrences(request)


@router.put("/updatestats")
async def update_stats(
    service: AnalyticsService = Depends(get_analytics_service),
):
    service.build_annotation_stats()


@router.post("/events")
async def events(
    request: AnnotationEventRequest,
    service: AnalyticsService = Depends(get_analytics_service),
):
    return service.get_annotation_events(request)
