from typing import Annotated

from fastapi import APIRouter, Depends, status

from lang3s.core.logger import get_logger
from lang3s.data.repositories.job_repository import JobRepository
from lang3s.data.schemas import Job
from lang3s.data.schemas.job import JobCreateRequest, JobListResponse, JobUpdateRequest
from lang3s.services.helpers import DBSessionDep, ErrorDetail

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
async def get_job(job_id: int, repository: JobRepositoryDep):
    return await repository.get(job_id)


@jobs_router.delete(
    "/id/{job_id}",
    response_model=bool,
    status_code=status.HTTP_200_OK,
    operation_id="jobsDeleteJob",
    responses={
        200: {"model": bool},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
        404: {"model": ErrorDetail},
    },
)
async def delete_job(job_id: int, repository: JobRepositoryDep):
    return await repository.delete(job_id)


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
async def list_jobs(repository: JobRepositoryDep):
    return await repository.list_jobs()


@jobs_router.post(
    "",
    response_model=Job,
    status_code=status.HTTP_201_CREATED,
    operation_id="jobsCreateJob",
    responses={
        201: {"model": Job},
        401: {"model": ErrorDetail},
        400: {"model": ErrorDetail},
    },
)
def create_job(payload: JobCreateRequest, repository: JobRepositoryDep):
    return payload


@jobs_router.put(
    "",
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
def update_job(payload: JobUpdateRequest, repository: JobRepositoryDep):
    return repository.update(payload)
