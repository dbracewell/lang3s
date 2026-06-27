import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, WithJsonSchema

from lang3s.data.models.job import JobStatus, JobType


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    status: JobStatus
    type_: JobType
    user_id: str
    total: int
    completed: int
    failed: int
    created_at: datetime.datetime
    started_at: Annotated[
        datetime.datetime | None,
        WithJsonSchema({"type": "string", "format": "date-time", "nullable": True}),
    ] = None
    completed_at: Annotated[
        datetime.datetime | None,
        WithJsonSchema({"type": "string", "format": "date-time", "nullable": True}),
    ] = None
    api_key: Annotated[
        str | None,
        WithJsonSchema({"type": "string", "nullable": True}),
    ] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @property
    def progress(self) -> float:
        if self.total:
            return (self.completed + self.failed) / self.total * 100
        return 0


class JobCreateRequest(BaseModel):
    name: str
    type_: JobType
    user_id: Annotated[
        str | None,
        WithJsonSchema({"type": "string", "nullable": True}),
    ] = None
    total: Annotated[int, WithJsonSchema({"type": "integer"})] = None
    api_key: Annotated[
        str | None,
        WithJsonSchema({"type": "string", "nullable": True}),
    ] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class JobUpdateRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: JobStatus | None = None
    total: int = 0
    completed: int = 0
    failed: int = 0
    metadata_json: dict[str, Any] | None = None


class JobMessage(BaseModel):
    job_id: int
    content: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = Field(default=JobStatus.Running)


class JobListResponse(RootModel[list[Job]]):
    pass
