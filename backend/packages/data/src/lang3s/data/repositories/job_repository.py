import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.exceptions import BadDataException, NotFoundException
from lang3s.core.schemas import File
from lang3s.data.constants import ANNOTATION_QUEUE_NAME
from lang3s.data.db import drop_indexes
from lang3s.data.models import Job as JobModel
from lang3s.data.models import TextAnnotation
from lang3s.data.models.job import JobStatus, JobType
from lang3s.data.schemas import Job as JobSchema
from lang3s.data.schemas.job import (
    JobCreateRequest,
    JobListResponse,
    JobMessage,
    JobUpdateRequest,
)


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, job_id: int) -> JobSchema:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()
        return JobSchema.model_validate(job)

    async def delete(self, job_id: int) -> bool:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()
        await self._session.delete(job)
        await self._session.commit()
        return True

    async def list_jobs(self) -> JobListResponse:
        result = await self._session.scalars(select(JobModel))
        return JobListResponse.model_validate(
            [JobSchema.model_validate(job) for job in result.all()]
        )

    async def create(
        self,
        create_request: JobCreateRequest,
    ) -> JobSchema:
        job = JobModel(
            name=create_request.name,
            type_=create_request.type_,
            total=create_request.total or 0,
            user_id=create_request.user_id or "1",
            metadata_json=create_request.metadata_json,
            api_key=create_request.api_key,
        )
        self._session.add(job)
        await self._session.commit()
        new_job = JobSchema.model_validate(job)
        async with RedisAsyncClient() as client:
            await client.publish_job_update(new_job)

        return new_job

    async def update(self, job_update: JobUpdateRequest) -> None:
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
                existing_job.status == JobStatus.Waiting
                and job_update.status != JobStatus.Waiting
            ):
                existing_job.started_at = datetime.datetime.now()
            if job_update.status in [
                JobStatus.Failed,
                JobStatus.Completed,
                JobStatus.Cancelled,
            ]:
                existing_job.completed_at = datetime.datetime.now()
            existing_job.status = job_update.status
        if job_update.metadata_json:
            existing_job.metadata_json.update(job_update.metadata_json)

        await self._session.merge(existing_job)
        await self._session.refresh(existing_job)
        await self._session.commit()
        async with RedisAsyncClient() as client:
            await client.publish_job_update(JobSchema.model_validate(existing_job))

    async def annotate(
        self,
        job_id: int,
        files: Iterable[File],
        limit: int = 0,
    ) -> None:
        limit = limit if limit >= 0 else 0
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()

        if job.status != JobStatus.Running:
            result = await self._session.scalars(
                select(JobModel).where(
                    JobModel.id != job_id,
                    JobModel.status == JobStatus.Running,
                    JobModel.type_ == JobType.Annotation,
                )
            )
            running_jobs = result.all()
            if running_jobs:
                raise BadDataException("Running annotation Job already exist")

        if job.status in [JobStatus.Waiting, JobStatus.Running]:
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
                for file in files:
                    await client.enqueue(
                        ANNOTATION_QUEUE_NAME,
                        JobMessage(job_id=job_id, content=file.model_dump()),
                    )
                    total_files += 1
                    if 0 < limit <= total_files:
                        break

                await client.enqueue(
                    ANNOTATION_QUEUE_NAME,
                    JobMessage(job_id=job_id, status=JobStatus.Completed),
                )

            await self.update(
                JobUpdateRequest(id=job_id, total=total_files, status=JobStatus.Running)
            )

        else:
            raise BadDataException()
