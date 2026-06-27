import uuid

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lang3s.core.exceptions import BadDataException, NotFoundException
from lang3s.data.models import Document, TextAnnotation
from lang3s.data.models.global_metadata import GlobalMetadata as GlobalMetadataModel
from lang3s.data.models.global_metadata import MetadataSource
from lang3s.data.schemas.global_metadata import (
    GlobalMetadata as GlobalMetadataSchema,
)
from lang3s.data.schemas.global_metadata import (
    GlobalMetadataAvailable,
    GlobalMetadataAvailableList,
    GlobalMetadataBySource,
    GlobalMetadataLinkedSource,
    GlobalMetadataList,
    GlobalMetadataUpdate,
)


class MetadataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_schema(self, model: GlobalMetadataSchema) -> GlobalMetadataSchema:
        schema_obj = GlobalMetadataSchema.model_validate(model)
        if model.linked_to:
            schema_obj.linked_to = self._to_schema(model.linked_to)
        return schema_obj

    async def get_all(self) -> GlobalMetadataList:
        r = await self.session.scalars(
            select(GlobalMetadataModel).options(
                selectinload(GlobalMetadataModel.linked_to)
            )
        )
        metadata_obj = []
        for m in r.all():
            metadata_obj.append(self._to_schema(m))
        return GlobalMetadataList(items=metadata_obj)

    async def get_all_by_source(self) -> GlobalMetadataBySource:
        r = await self.get_all()
        by_source = GlobalMetadataBySource(
            documents={},
            sentences={},
            annotations={},
        )
        for entry in r.items:
            new_entry = GlobalMetadataLinkedSource(
                id=entry.id,  # type: ignore
                name=entry.name,
                source=entry.source,
                links_to_metadata_id=entry.links_to_metadata_id,
                data_type=entry.data_type,
                formatter=entry.formatter,
                linked_source=entry.linked_to.source if entry.linked_to else None,
                linked_name=entry.linked_to.name if entry.linked_to else None,
            )
            if entry.source == MetadataSource.annotation:
                by_source.documents[entry.name] = new_entry
            elif entry.source == MetadataSource.sentence:
                by_source.sentences[entry.name] = new_entry
            else:
                by_source.documents[entry.name] = new_entry
        return by_source

    async def get_by_id(self, id: uuid.UUID) -> GlobalMetadataSchema:
        r = await self.session.get(GlobalMetadataModel, id)
        if r is None:
            raise NotFoundException()
        return GlobalMetadataSchema.model_validate(r)

    async def delete_by_id(self, id: uuid.UUID) -> bool:
        r = await self.session.get(GlobalMetadataModel, id)
        if r is None:
            raise NotFoundException()
        await self.session.delete(r)
        await self.session.commit()
        return True

    async def update(self, item: GlobalMetadataUpdate) -> bool:
        existing_item = await self.session.get(GlobalMetadataModel, item.id)
        if existing_item is None:
            raise NotFoundException()
        if item.source:
            existing_item.source = item.source
        if item.name:
            existing_item.name = item.name
        if item.data_type:
            existing_item.data_type = item.data_type
        if item.formatter:
            existing_item.formatter = item.formatter
        if item.links_to_metadata_id:
            parent = await self.session.get(
                GlobalMetadataModel, item.links_to_metadata_id
            )
            if not parent:
                raise NotFoundException()
            existing_item.linked_to = parent  # type: ignore

        await self.session.merge(existing_item)
        await self.session.commit()
        return True

    async def add(self, item: GlobalMetadataSchema) -> GlobalMetadataSchema:
        parent = await self._get_or_create(item.linked_to) if item.linked_to else None
        existing_item = await self.session.scalar(
            select(GlobalMetadataModel).filter_by(source=item.source, name=item.name)
        )

        if existing_item:
            raise BadDataException()

        new_item = GlobalMetadataModel(
            **item.model_dump(exclude={"linked_to", "id"}),
            linked_to=parent,
        )
        self.session.add(new_item)
        await self.session.commit()
        await self.session.refresh(new_item)

        return GlobalMetadataSchema.model_validate(new_item)

    async def _get_or_create(self, item: GlobalMetadataSchema) -> GlobalMetadataModel:
        if item.id:
            item_model = await self.session.get(GlobalMetadataModel, item.id)
            if not item_model:
                raise NotFoundException()
            return item_model  # type: ignore

        parent_of_parent = (
            await self._get_or_create(item.linked_to) if item.linked_to else None
        )

        new_model = GlobalMetadataModel(
            **item.model_dump(exclude={"linked_to", "id"}), linked_to=parent_of_parent
        )

        return new_model

    async def probe(self) -> GlobalMetadataAvailableList:
        existing = set([f"{m.source}-{m.name}" for m in (await self.get_all()).items])
        sentence_stmt = (
            select(
                literal("sentences").label("source"),
                func.jsonb_object_keys(TextAnnotation.metadata_json).label("key"),
            )
            .distinct()
            .where(TextAnnotation.type_ == "sentence")
        )
        annotation_stmt = (
            select(
                literal("annotations").label("source"),
                func.jsonb_object_keys(TextAnnotation.metadata_json).label("key"),
            )
            .distinct()
            .where(TextAnnotation.type_ != "sentence")
        )
        document_stmt = select(
            literal("documents").label("source"),
            func.jsonb_object_keys(Document.metadata_json).label("key"),
        ).distinct()
        union = sentence_stmt.union_all(annotation_stmt, document_stmt)
        result = await self.session.execute(union)
        filtered: list[GlobalMetadataAvailable] = []
        for source, key in result.fetchall():
            if f"{source}-{key}" not in existing:
                filtered.append(GlobalMetadataAvailable(source=source, key=key))
        return GlobalMetadataAvailableList.model_validate(filtered)
