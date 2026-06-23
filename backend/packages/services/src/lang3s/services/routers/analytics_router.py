from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.logger import get_logger
from lang3s.services.analytics import get_analytics_db
from lang3s.services.models.analytics_models import (
    AnnotationCohortInformationRequest,
    AnnotationCoOccurrenceRequest,
    AnnotationCountsRequest,
    AnnotationEventRequest,
    AnnotationMetricRequest,
)
from lang3s.services.repositories.analytics_repository import AnalyticsRepository

logger = get_logger(__name__)

analytics_router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)


def get_analytics_repository():
    return AnalyticsRepository(get_analytics_db())


type AnalyticsRepositoryDep = Annotated[
    AnalyticsRepository, Depends(get_analytics_repository)
]


@analytics_router.get("/topic/{id}")
async def get_topic(id: str, repository: AnalyticsRepositoryDep):
    return repository.get_ranked_entities_for_topic(id)


@analytics_router.post("/cohortinformation")
async def cohort_information(
    payload: AnnotationCohortInformationRequest,
    repository: AnalyticsRepositoryDep,
):
    return repository.get_annotation_cohort_information(payload)


@analytics_router.post("/cohorts")
async def cohorts(repository: AnalyticsRepositoryDep):
    return repository.get_annotation_cohorts()


@analytics_router.post("/topicscore")
async def topic_score(
    payload: AnnotationMetricRequest,
    repository: AnalyticsRepositoryDep,
):
    return repository.get_annotation_topic_score_metrics(payload)


@analytics_router.post("/affinity")
async def loaners(
    payload: AnnotationMetricRequest,
    repository: AnalyticsRepositoryDep,
):
    return repository.get_annotation_affinity_metrics(payload)


@analytics_router.post("/counts")
async def counts(
    payload: AnnotationCountsRequest,
    repository: AnalyticsRepositoryDep,
):
    print(payload)
    return repository.get_annotation_counts(payload)


@analytics_router.post("/cooccurrence")
async def co_occurrence(
    payload: AnnotationCoOccurrenceRequest,
    repository: AnalyticsRepositoryDep,
):
    return repository.get_annotation_co_occurrences(payload)


@analytics_router.put("/updatestats")
async def update_stats(
    repository: AnalyticsRepositoryDep,
):
    repository.build_annotation_stats()


@analytics_router.post("/events")
async def events(
    payload: AnnotationEventRequest,
    repository: AnalyticsRepositoryDep,
):
    return repository.get_annotation_events(payload)
