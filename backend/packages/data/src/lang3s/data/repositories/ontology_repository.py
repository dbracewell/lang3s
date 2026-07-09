from typing import Dict, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy_utils import Ltree

from lang3s.core.collections_extras import hashed_select
from lang3s.core.constants import COLOR_NAMES
from lang3s.core.exceptions import NotFoundException
from lang3s.data.models import AnnotationOntologyMapping, TextAnnotation
from lang3s.data.models import Ontology as OntologyModel
from lang3s.data.schemas.ontology import (
    AnnotationIdOntologyMapping,
    AnnotationOntologyMappingList,
    IsolatedOntologyEntry,
    OntologyEntry,
    OntologyEntryCreationRequest,
    OntologyPaths,
    OntologyUpdateRequest,
    PotentialMappingList,
)
from lang3s.data.schemas.ontology import Ontology as OntologySchema


class OntologyRepository:
    def __init__(self, session: AsyncSession | Session):
        self.session = session

    def _build_schema(self, models: Sequence[OntologyModel]):
        sorted_models = sorted(models, key=lambda m: len(m.path.path.split(".")))
        flat_nodes = [
            IsolatedOntologyEntry.model_validate(node) for node in sorted_models
        ]
        rooted_nodes = [OntologyEntry(**node.model_dump()) for node in flat_nodes]
        schema_map: Dict[int, OntologyEntry] = {node.id: node for node in rooted_nodes}  # type:ignore
        root: OntologyEntry | None = None

        for node in rooted_nodes:
            if node.parent_id:
                schema_map[node.parent_id].children.append(node)
                node.parent_node = schema_map[node.parent_id]
            elif root is None:
                root = node
            else:
                raise ValueError("Invalid state more than one root in the Ontology")

        root: OntologyEntry = root or OntologyEntry.root()
        return OntologySchema(root=root)

    async def load_ontology(self) -> OntologySchema:
        if isinstance(self.session, AsyncSession):
            stmt = (
                select(OntologyModel)
                .order_by(func.nlevel(OntologyModel.path))
                .options(selectinload(OntologyModel.mappings))
            )
            result = await self.session.scalars(stmt)
            return self._build_schema(result.all())
        raise Exception("Invalid state initialized with Session")

    def sync_load_ontology(self) -> OntologySchema:
        if isinstance(self.session, Session):
            stmt = (
                select(OntologyModel)
                .order_by(func.nlevel(OntologyModel.path))
                .options(selectinload(OntologyModel.mappings))
            )
            result = self.session.scalars(stmt)
            return self._build_schema(result.all())
        raise Exception("Invalid state initialized with AsyncSession")

    def _prepare_update(self, ontology_schema: OntologySchema) -> list[OntologyModel]:
        models: list[OntologyModel] = []
        nodes = [ontology_schema.root]

        while nodes:
            node = nodes.pop()
            nodes.extend(node.children)

            seen_mappings = set()
            node_mappings: list[AnnotationOntologyMapping] = []
            sorted_mappings = sorted(node.mappings, key=lambda x: (x.id is None, x.id))
            for m in sorted_mappings:
                if m.mapping not in seen_mappings:
                    seen_mappings.add(m.mapping)
                    node_mappings.append(AnnotationOntologyMapping(**m.model_dump()))

            model = OntologyModel(
                id=node.id if node.id else None,  # type: ignore
                name=node.name,
                path=Ltree(node.path),
                parent_id=node.parent_id,
                properties={
                    k: v.model_dump()
                    for k, v in node.properties.items()
                    if v.definedBy is None
                },
                mappings=node_mappings,
                description=node.description,
                color=node.color,
            )
            models.append(model)

        return models

    async def update_ontology(self, ontology_schema: OntologySchema) -> OntologySchema:
        if isinstance(self.session, AsyncSession):
            for model in self._prepare_update(ontology_schema):
                await self.session.merge(model)
            await self.session.commit()
            return await self.load_ontology()
        raise Exception("Invalid state initialized with Session")

    def sync_update_ontology(self, ontology_schema: OntologySchema) -> OntologySchema:
        if isinstance(self.session, Session):
            for model in self._prepare_update(ontology_schema):
                self.session.merge(model)
            self.session.commit()
            return self.sync_load_ontology()
        raise Exception("Invalid state initialized with AsyncSession")

    async def get_annotations_for_document(
        self,
        document_id: str,
    ) -> AnnotationOntologyMappingList:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")

        stmt = (
            select(
                TextAnnotation.id,
                OntologyModel.name,
                OntologyModel.path,
                OntologyModel.color,
            )
            .join(
                AnnotationOntologyMapping,
                TextAnnotation.mapping == AnnotationOntologyMapping.mapping,
            )
            .join(
                OntologyModel, AnnotationOntologyMapping.ontology_id == OntologyModel.id
            )
            .where(TextAnnotation.document_id == document_id)
        )
        r = await self.session.execute(stmt)
        mappings: dict[str, AnnotationIdOntologyMapping] = {}
        path: Ltree
        for aid, name, path, color in r.all():
            mappings[aid] = AnnotationIdOntologyMapping(
                annotation_id=aid,
                name=name,
                color=color,
                path=path.path,
            )
        return AnnotationOntologyMappingList(mapping=mappings)

    async def update_entry(self, request: OntologyUpdateRequest) -> bool:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")
        entry = await self.session.get(OntologyModel, request.id)
        if not entry:
            raise NotFoundException()

        to_delete = []
        if request.color:
            entry.color = request.color
        if request.description:
            entry.description = request.description
        if request.mapping is not None:
            new_mappings = []
            for m in request.mapping:
                if not m:
                    continue
                existing = None
                for k in entry.mappings:
                    if k.mapping == m:
                        existing = k
                        break
                if existing:
                    new_mappings.append(existing)
                else:
                    new_mappings.append(
                        AnnotationOntologyMapping(
                            mapping=m,
                            ontology_id=request.id,
                        )
                    )
            for m in entry.mappings:
                if m not in new_mappings:
                    to_delete.append(m)
            entry.mappings = new_mappings
        if request.properties is not None:
            entry.properties = {
                k: v.model_dump() for k, v in request.properties.items()
            }

        for item in to_delete:
            await self.session.delete(item)
        await self.session.merge(entry)
        await self.session.commit()
        return True

    async def delete_entry(self, node_id: int) -> bool:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")
        r = await self.session.get(OntologyModel, node_id)
        if not r:
            raise NotFoundException()
        await self.session.delete(r)
        await self.session.commit()
        return True

    async def add_entry(self, request: OntologyEntryCreationRequest) -> bool:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")

        parent = await self.session.get(OntologyModel, request.parent_id)
        if not parent:
            raise NotFoundException()

        entry = OntologyModel(
            parent_id=request.parent_id,
            name=request.name,
            description=request.description,
            color=hashed_select(request.name, COLOR_NAMES),
            path=Ltree(f"{parent.path}.{request.name}"),
        )
        self.session.add(entry)
        await self.session.commit()
        return True

    async def name_exists(self, name: str) -> bool:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")
        stmt = select(OntologyModel.name).where(OntologyModel.name == name)
        r = await self.session.execute(stmt)
        return r.all() is not None

    async def get_node_path(self, path: str) -> OntologyPaths:
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")

        stmt = (
            select(OntologyModel.path)
            .where(OntologyModel.path.descendant_of(Ltree(path)))
            .order_by(OntologyModel.path.asc())
        )
        r = await self.session.execute(stmt)
        valid_strings = [str(p) for p in r.scalars().all()]
        return OntologyPaths.model_validate(valid_strings)

    async def get_all_potential_mappings(self):
        if not isinstance(self.session, AsyncSession):
            raise Exception("Invalid state initialized with AsyncSession")
        stmt = (
            select(TextAnnotation.mapping, OntologyModel.path)
            .distinct()
            .select_from(TextAnnotation)
            .join(
                AnnotationOntologyMapping,
                TextAnnotation.mapping == AnnotationOntologyMapping.mapping,
                isouter=True,
            )
            .join(
                OntologyModel,
                AnnotationOntologyMapping.ontology_id == OntologyModel.id,
                isouter=True,
            )
            .where(
                TextAnnotation.type_ != "sentence",
                TextAnnotation.mapping.is_not(None),
            )
            .order_by(TextAnnotation.mapping.asc())
        )
        r = await self.session.execute(stmt)
        d = {m: p.path if p is not None else None for m, p in r.all()}
        return PotentialMappingList(items=d)
