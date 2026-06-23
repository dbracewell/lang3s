from typing import Any, Iterable, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.operators import op

from lang3s.core.clients import RedisAsyncClient
from lang3s.core.exceptions import BadDataException, NotFoundException
from lang3s.core.schemas import File
from lang3s.data.constants import ANNOTATION_QUEUE_NAME
from lang3s.data.db import drop_indexes
from lang3s.data.models import Job as JobModel
from lang3s.data.models import TextAnnotation
from lang3s.data.models.job import JobStatus, JobType
from lang3s.data.schemas import Job as JobSchema
from lang3s.data.schemas.job import JobMessage


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, job_id: int) -> JobSchema:
        job = await self._session.get(JobModel, job_id)
        if job is None:
            raise NotFoundException()
        return JobSchema.model_validate(job)

    async def create(
        self,
        *,
        name: str,
        type_: JobType,
        total: int = 0,
        metadata_json: Optional[dict[str, Any]] = None,
    ) -> JobSchema:
        job = JobModel(
            name=name,
            type_=type_,
            total=total,
            user_id="1",
            metadata_json=metadata_json or {},
        )
        self._session.add(job)
        await self._session.commit()
        return JobSchema.model_validate(job)

    async def update(
        self,
        job_id: int,
        *,
        total: int = 0,
        completed: int = 0,
        failed: int = 0,
        status: Optional[JobStatus] = None,
        metadata_json: Optional[dict[str, Any]] = None,
    ) -> None:
        update_values = {}
        if total:
            update_values["total"] = JobModel.total + total
        if completed:
            update_values["completed"] = JobModel.completed + completed
        if failed:
            update_values["failed"] = JobModel.failed + failed
        if status:
            update_values["status"] = status
        if metadata_json:
            update_values["metadata_json"] = op(
                JobModel.metadata_json, "||", metadata_json
            )
        stmt = update(JobModel).where(JobModel.id == job_id).values(**update_values)
        await self._session.execute(stmt)
        await self._session.commit()

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
                job_id=job_id,
                total=total_files,
                status=JobStatus.Running,
            )

        else:
            raise BadDataException()
