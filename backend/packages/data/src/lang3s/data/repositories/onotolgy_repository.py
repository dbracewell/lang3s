from typing import Dict, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload
from sqlalchemy_utils import Ltree

from lang3s.data.models import AnnotationOntologyMapping
from lang3s.data.models import Ontology as OntologyModel
from lang3s.data.schemas.ontology import IsolatedOntologyEntry, OntologyEntry
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
