from typing import Annotated, List

from fastapi import APIRouter, Depends, status
from pydantic import RootModel

from lang3s.core.logger import get_logger
from lang3s.data.db import get_db_session
from lang3s.data.repositories.job_repository import JobRepository
from lang3s.data.schemas import Job
from lang3s.services.helpers import ErrorDetail

logger = get_logger(__name__)

jobs_router = APIRouter(
    prefix="/job",
    tags=["Jobs"],
    responses={404: {"description": "Not found"}},
)


def get_jobs_repository():
    return JobRepository(get_db_session())


type JobRepositoryDep = Annotated[JobRepository, Depends(get_jobs_repository)]


@jobs_router.get(
    "/id/{job-id}",
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
def get_job(job_id: int, repository: JobRepositoryDep):
    return repository.get(job_id)


class JobListResponse(RootModel[List[Job]]):
    pass


@jobs_router.get(
    "/",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    operation_id="jobsListJobs",
    responses={
        200: {"model": JobListResponse},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
def list_jobs(repository: JobRepositoryDep):
    return []


@jobs_router.post(
    "/",
    response_model=Job,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobsCreateJob",
    responses={
        201: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
def create_job(payload: Job, repository: JobRepositoryDep):
    return payload


@jobs_router.put(
    "/",
    response_model=Job,
    status_code=status.HTTP_200_OK,
    operation_id="jobsUpdateJob",
    responses={
        200: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
def update_job(payload: Job, repository: JobRepositoryDep):
    return repository.update(payload)
