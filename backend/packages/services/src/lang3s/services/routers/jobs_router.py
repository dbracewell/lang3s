from typing import Annotated

from fastapi import APIRouter, Depends, status

from lang3s.core.config import config
from lang3s.core.exceptions import NotFoundException, UnauthorizedException
from lang3s.core.logger import get_logger
from lang3s.core.schemas.job import (
    JobAnnotateRequest,
    JobCreateRequest,
    JobListResponse,
    JobType,
    JobUpdateRequest,
)
from lang3s.data.events import EventType
from lang3s.data.repositories.job_repository import JobRepository
from lang3s.data.schemas import Job
from lang3s.services.helpers import DBSessionDep, ErrorDetail, RedisDep
from lang3s.services.permissions import Permissions
from lang3s.services.security import (
    AuthenticatedUserDep,
)

logger = get_logger(__name__)

jobs_router = APIRouter(
    prefix="/job",
    tags=["Jobs"],
    responses={404: {"description": "Not found"}},
)


def get_jobs_repository(session: DBSessionDep):
    return JobRepository(session)


type JobRepositoryDep = Annotated[JobRepository, Depends(get_jobs_repository)]


@jobs_router.get(
    "/id/{job_id}",
    response_model=Job,
    status_code=status.HTTP_200_OK,
    operation_id="jobsGetJob",
    responses={
        200: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_job(
    job_id: int,
    repository: JobRepositoryDep,
    user: AuthenticatedUserDep,
):
    if not user.has_permission(Permissions.job.get):
        raise UnauthorizedException()
    return await repository.get(job_id)


@jobs_router.get(
    "/running/{job_type}",
    response_model=int,
    operation_id="jobsGetRunningCount",
    responses={
        200: {"model": int},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def get_running_count(
    job_type: JobType,
    repository: JobRepositoryDep,
    user: AuthenticatedUserDep,
):
    if user is None:
        raise UnauthorizedException()
    if not user.has_permission(Permissions.ontology.edit):
        raise UnauthorizedException()
    return await repository.get_running_count(job_type)


@jobs_router.delete(
    "/id/{job_id}",
    response_model=Job,
    status_code=status.HTTP_200_OK,
    operation_id="jobsDeleteJob",
    responses={
        200: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def delete_job(
    job_id: int,
    repository: JobRepositoryDep,
    user: AuthenticatedUserDep,
    redis: RedisDep,
):
    if user is None or not user.has_permission(Permissions.job.delete):
        raise UnauthorizedException()
    job = await repository.delete(job_id)
    job.deleting = True
    await redis.publish_event(
        event_type=EventType.JOB_UPDATE,
        user_id=user.user_id,
        payload=job.model_dump(mode="json"),
    )
    return job


@jobs_router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="jobsListJobs",
    responses={
        200: {"model": JobListResponse},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
async def list_jobs(
    repository: JobRepositoryDep,
    user: AuthenticatedUserDep,
):
    if not user.has_permission(Permissions.job.list):
        raise UnauthorizedException()
    return await repository.list_jobs()


@jobs_router.post(
    "",
    response_model=Job,
    operation_id="jobsCreateJob",
    responses={
        201: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        422: {"model": ErrorDetail},
    },
)
async def create_job(
    payload: JobCreateRequest,
    repository: JobRepositoryDep,
    redis: RedisDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.job.create):
        raise UnauthorizedException()
    new_job = await repository.create(payload, user.user_id)
    await redis.publish_event(
        event_type=EventType.JOB_UPDATE,
        user_id=user.user_id,
        payload=new_job.model_dump(mode="json"),
    )
    return new_job


@jobs_router.put(
    "",
    response_model=Job,
    operation_id="jobsUpdateJob",
    responses={
        200: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def update_job(
    payload: JobUpdateRequest,
    repository: JobRepositoryDep,
    redis: RedisDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.job.create):
        raise UnauthorizedException()
    job = await repository.get(payload.id)
    if job is None:
        raise NotFoundException()
    if user.role != "admin" and user.role != config.SYSTEM_KEY:
        if job.user_id != user.user_id:
            raise UnauthorizedException()
    updated_job = await repository.update(payload)
    await redis.publish_event(
        event_type=EventType.JOB_UPDATE,
        user_id=user.user_id,
        payload=updated_job.model_dump(mode="json"),
    )
    return updated_job


@jobs_router.post(
    "/annotate",
    response_model=Job,
    operation_id="jobsAnnotate",
    responses={
        200: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def annotate(
    payload: JobAnnotateRequest,
    repository: JobRepositoryDep,
    redis: RedisDep,
    user: AuthenticatedUserDep,
):
    if user is None or not user.has_permission(Permissions.job.create):
        raise UnauthorizedException()
    job = await repository.get(payload.id)
    if job is None:
        raise NotFoundException()
    if user.role != "admin" and user.role != config.SYSTEM_KEY:
        if job.user_id != user.user_id:
            raise UnauthorizedException()

    updated_job = await repository.annotate(payload)
    await redis.publish_event(
        event_type=EventType.JOB_UPDATE,
        user_id=user.user_id,
        payload=updated_job.model_dump(mode="json"),
    )
    return updated_job
