import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from lang3s.core.schemas.job import JobStatus, JobType

from . import Base


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(
        Integer,
        autoincrement=True,
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        "name",
        String,
        index=True,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        "status",
        Enum(JobStatus, name="job_status_enum"),
        index=True,
        default=JobStatus.Waiting,
    )
    type_: Mapped[JobType] = mapped_column(
        "type",
        Enum(JobType, name="job_type_enum"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    total: Mapped[int] = mapped_column(
        "total",
        Integer,
        default=0,
    )
    completed: Mapped[int] = mapped_column(
        "completed",
        Integer,
        default=0,
    )
    failed: Mapped[int] = mapped_column(
        "failed",
        Integer,
        default=0,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        "started_at",
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        "completed_at",
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
