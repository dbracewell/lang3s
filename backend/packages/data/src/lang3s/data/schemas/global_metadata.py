from __future__ import annotations

import uuid
from typing import Annotated, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    WithJsonSchema,
)

from lang3s.data.models.global_metadata import DataType, MetadataSource


class GlobalMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Annotated[
        uuid.UUID | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    source: MetadataSource
    name: str
    data_type: DataType
    formatter: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    links_to_document_id: bool = False
    links_to_metadata_id: Annotated[
        uuid.UUID | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    linked_to: Optional[GlobalMetadata] = None


class GlobalMetadataList(BaseModel):
    items: List[GlobalMetadata] = Field(default_factory=list)


class GlobalMetadataLinkedSource(GlobalMetadata):
    id: uuid.UUID
    linked_name: Annotated[
        str | None, WithJsonSchema({"type": "string", "nullable": True})
    ] = None
    linked_source: MetadataSource | None = None


class GlobalMetadataBySource(BaseModel):
    documents: dict[str, GlobalMetadataLinkedSource]
    annotations: dict[str, GlobalMetadataLinkedSource]
    sentences: dict[str, GlobalMetadataLinkedSource]


class GlobalMetadataAvailable(BaseModel):
    source: str
    key: str


class GlobalMetadataAvailableList(RootModel[list[GlobalMetadataAvailable]]):
    pass


class GlobalMetadataUpdate(BaseModel):
    id: uuid.UUID
    source: MetadataSource | None = None
    name: str | None = None
    data_type: DataType | None = None
    formatter: str | None = None
    links_to_document_id: bool = False
    links_to_metadata_id: uuid.UUID | None = None
