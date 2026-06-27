from __future__ import annotations

import enum
import uuid
from typing import Optional

from sqlalchemy import (
    UUID,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class DataCategory(enum.StrEnum):
    string = "string"
    number = "number"
    boolean = "boolean"
    date = "date"
    none = "none"


class DataType(enum.StrEnum):
    string = "string"
    string_array = "string_array"
    int = "int"
    float = "float"
    boolean = "boolean"
    date = "date"

    @property
    def category(self):
        match self:
            case DataType.string | DataType.string_array:
                return DataCategory.string
            case DataType.int | DataType.float:
                return DataCategory.number
            case DataType.boolean:
                return DataCategory.boolean
            case DataType.date:
                return DataCategory.date


class MetadataSource(enum.StrEnum):
    document = "document"
    annotation = "annotation"
    sentence = "sentence"


class GlobalMetadata(Base):
    __tablename__ = "global_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        "id",
        UUID,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        primary_key=True,
    )
    source: Mapped[MetadataSource] = mapped_column(
        "source",
        Enum(MetadataSource),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        "name",
        String,
        nullable=False,
    )
    formatter: Mapped[Optional[str]] = mapped_column(
        "formatter",
        String,
        nullable=True,
    )
    data_type: Mapped[DataType] = mapped_column(
        "data_type",
        Enum(DataType),
        nullable=False,
    )
    links_to_document_id: Mapped[bool] = mapped_column(
        "links_to_document_id",
        Boolean,
        default=False,
        nullable=False,
    )
    links_to_metadata_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "links_to_metadata_id",
        ForeignKey("global_metadata.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    linked_to: Mapped[Optional[GlobalMetadata]] = relationship(
        "GlobalMetadata",
        remote_side=[id],
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "idx_global_metadata_source_name",
            "source",
            "name",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<GlobalMetadata id={self.id} source={self.source} name={self.name}>"
