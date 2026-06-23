import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from lang3s.data.models.job import JobStatus, JobType


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    status: JobStatus
    type_: JobType
    user_id: str
    total: int = 0
    completed: int = 0
    failed: int = 0
    created_at: datetime.datetime
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    api_key: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class JobMessage(BaseModel):
    job_id: int
    content: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = Field(default=JobStatus.Running)
