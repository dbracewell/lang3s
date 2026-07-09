from typing import Annotated

from fastapi import APIRouter, Depends

from lang3s.core.exceptions import UnauthorizedException
from lang3s.core.logger import get_logger
from lang3s.core.schemas.job import Job, JobStatus
from lang3s.data.events import EventType
from lang3s.services.analytics import get_analytics_db
from lang3s.services.helpers import ErrorDetail, RedisDep
from lang3s.services.permissions import Permissions
from lang3s.services.repositories.analytics_repository import AnalyticsRepository
from lang3s.services.schemas.analytics_api_schema import (
    AnnotationCohortInformationRequest,
    AnnotationCoOccurrenceRequest,
    AnnotationCoOccurrenceResult,
    AnnotationCountsRequest,
    AnnotationCountsResult,
    AnnotationEventRequest,
    AnnotationEventResult,
    AnnotationMetricRequest,
    AnnotationMetricResult,
    CohortClustering,
    CohortInformationResult,
)
from lang3s.services.security import (
    AuthenticatedUserDep,
)

logger = get_logger(__name__)

analytics_router = APIRouter(
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)


def get_analytics_repository():
    return AnalyticsRepository(get_analytics_db())


type AnalyticsRepositoryDep = Annotated[
    AnalyticsRepository, Depends(get_analytics_repository)
]


@analytics_router.get(
    "/topic/{id}",
    operation_id="topicGetById",
)
async def get_topic(
    id: str,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None:
        raise UnauthorizedException()
    return repository.get_ranked_entities_for_topic(id)


@analytics_router.post(
    "/cohortinformation",
    operation_id="cohortInformation",
    responses={
        200: {"model": CohortInformationResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def cohort_information(
    payload: AnnotationCohortInformationRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> CohortInformationResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_cohort_information(payload)


@analytics_router.post(
    "/cohorts",
    operation_id="cohorts",
    responses={
        200: {"model": CohortClustering},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def cohorts(
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> CohortClustering:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_cohorts()


@analytics_router.post(
    "/topicscore",
    operation_id="topicScore",
    responses={
        200: {"model": AnnotationMetricResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def topic_score(
    payload: AnnotationMetricRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationMetricResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_topic_score_metrics(payload)


@analytics_router.post(
    "/affinity",
    operation_id="affinityScore",
    responses={
        200: {"model": AnnotationMetricResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def loaners(
    payload: AnnotationMetricRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationMetricResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_affinity_metrics(payload)


@analytics_router.post(
    "/counts",
    operation_id="annotationCounts",
    responses={
        200: {"model": AnnotationCountsResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def counts(
    payload: AnnotationCountsRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationCountsResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_counts(payload)


@analytics_router.post(
    "/cooccurrence",
    operation_id="entityCoOccurrence",
    responses={
        200: {"model": AnnotationCoOccurrenceResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def co_occurrence(
    payload: AnnotationCoOccurrenceRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationCoOccurrenceResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_co_occurrences(payload)


@analytics_router.post(
    "/updatestats",
    operation_id="analysisUpdateStats",
    responses={
        200: {"model": bool},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def update_stats(
    job: Job,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
    redis: RedisDep,
):
    if user is None or not user.has_permission(
        Permissions.ontology.edit,
        Permissions.job.create,
    ):
        raise UnauthorizedException()
    repository.build_annotation_stats(job)
    await redis.publish_event(
        event_type=EventType.ANALYTICS_UPDATE,
        user_id=job.user_id,
        payload={"completed": True},
    )
    job.completed = 1
    job.status = JobStatus.Completed
    await redis.publish_event(
        event_type=EventType.JOB_UPDATE,
        user_id=job.user_id,
        payload=job.model_dump(mode="json"),
    )
    return True


@analytics_router.post(
    "/events",
    operation_id="entityEvents",
    responses={
        200: {"model": AnnotationEventResult},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def events(
    payload: AnnotationEventRequest,
    repository: AnalyticsRepositoryDep,
    user: AuthenticatedUserDep,
) -> AnnotationEventResult:
    if user is None:
        raise UnauthorizedException()
    return repository.get_annotation_events(payload)
