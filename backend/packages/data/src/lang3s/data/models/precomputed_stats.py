from typing import Any

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PreComputedStats(Base):
    __tablename__ = "precomputed_stats"

    id: Mapped[int] = mapped_column(
        "id",
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        "name",
        String,
        index=True,
        unique=True,
        nullable=False,
    )
    value: Mapped[dict[str, Any]] = mapped_column(
        "value",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )
