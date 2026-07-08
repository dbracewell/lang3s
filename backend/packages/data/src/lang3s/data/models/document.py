from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .text import Text


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(
        "id",
        String(22),
        primary_key=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        "title",
        String,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    )
    # This field allows arbitrary properties to be store on the document.
    # This could include things like language, urls, etc.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        MutableDict.as_mutable(JSONB),
        nullable=False,
        server_default="{}",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    text: Mapped[Text] = relationship(
        "Text",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "idx_documents_metadata_gin_idx",
            "metadata",
            postgresql_using="GIN",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<%s id={self.id}>" % self.__class__.__name__
