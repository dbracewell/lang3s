import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.exceptions import BadDataException, NotFoundException
from lang3s.core.exceptions.custom import TooManyRequests
from lang3s.core.schemas.job import (
    JobAnnotateRequest,
    JobCreateRequest,
    JobListResponse,
    JobMessage,
    JobStatus,
    JobType,
    JobUpdateRequest,
)
from lang3s.data.constants import ANNOTATION_QUEUE_NAME
from lang3s.data.db import drop_indexes
from lang3s.data.models import Job as JobModel
from lang3s.data.models import TextAnnotation
from lang3s.data.schemas import Job as JobSchema


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, job_id: int) -> JobSchema:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()
        return JobSchema.model_validate(job)

    async def get_running_count(self, job_type: JobType) -> int:
        stmt = select(func.count(JobModel.id)).where(
            JobModel.type_ == job_type,
            JobModel.status == JobStatus.Running,
        )
        return await self._session.scalar(stmt) or 0

    async def delete(self, job_id: int) -> JobSchema:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()
        await self._session.delete(job)
        await self._session.commit()
        return JobSchema.model_validate(job)

    async def list_jobs(self) -> JobListResponse:
        result = await self._session.scalars(select(JobModel))
        return JobListResponse.model_validate(
            [JobSchema.model_validate(job) for job in result.all()]
        )

    async def create(self, create_request: JobCreateRequest, user_id: str) -> JobSchema:
        job = JobModel(
            name=create_request.name,
            type_=create_request.type_,
            total=create_request.total or 0,
            user_id=user_id,
            metadata_json=create_request.metadata_json,
            status=create_request.status or JobStatus.Waiting,
            started_at=datetime.datetime.now(tz=datetime.timezone.utc)
            if create_request.status == JobStatus.Running
            else None,
        )
        self._session.add(job)
        await self._session.commit()
        return JobSchema.model_validate(job)

    async def update(
        self,
        job_update: JobUpdateRequest,
        existing_job: JobModel | None = None,
    ) -> JobSchema:
        if existing_job is None:
            existing_job = await self._session.get(JobModel, job_update.id)

        if not existing_job:
            raise NotFoundException()

        if job_update.total:
            existing_job.total += job_update.total
        if job_update.completed:
            existing_job.completed += job_update.completed
        if job_update.failed:
            existing_job.failed += job_update.failed
        if job_update.status:
            if (
                existing_job.status != JobStatus.Running
                and job_update.status == JobStatus.Running
            ):
                existing_job.started_at = datetime.datetime.now(
                    tz=datetime.timezone.utc
                )

            if job_update.status in [
                JobStatus.Failed,
                JobStatus.Completed,
                JobStatus.Cancelled,
            ]:
                existing_job.completed_at = datetime.datetime.now(
                    tz=datetime.timezone.utc
                )

            existing_job.status = job_update.status

        if job_update.metadata_json:
            existing_job.metadata_json.update(job_update.metadata_json)  # type:ignore

        await self._session.merge(existing_job)
        await self._session.refresh(existing_job)
        await self._session.commit()
        return JobSchema.model_validate(existing_job)

    async def annotate(
        self,
        payload: JobAnnotateRequest,
    ) -> JobSchema:
        job = await self._session.get(JobModel, payload.id)
        if job is None:
            raise NotFoundException()

        r = await self._session.scalars(
            select(JobModel).where(
                JobModel.type_ == JobType.Annotation,
                JobModel.status == JobStatus.Running,
                JobModel.id != payload.id,
            )
        )
        running_jobs = r.all()
        if len(running_jobs) > 0:
            raise TooManyRequests()

        if job.status not in [JobStatus.Waiting, JobStatus.Running]:
            raise BadDataException()

        if job.status == JobStatus.Waiting:
            await drop_indexes(
                TextAnnotation,
                [
                    "idx_text_annotations_embedding_hnsw",
                    "ix_text_annotations_sentence_non_stopword_hnsw",
                ],
            )

        total_files = 0
        async with RedisAsyncClient() as client:
            for file in payload.files:
                await client.enqueue(
                    ANNOTATION_QUEUE_NAME,
                    JobMessage(job_id=payload.id, content=file.model_dump()),
                )
                total_files += 1

            if payload.complete:
                await client.enqueue(
                    ANNOTATION_QUEUE_NAME,
                    JobMessage(job_id=payload.id, status=JobStatus.Completed),
                )

        updated_job = await self.update(
            JobUpdateRequest(
                status=JobStatus.Running,
                total=total_files,
                id=payload.id,
            ),
            existing_job=job,  # type: ignore
        )

        return updated_job
