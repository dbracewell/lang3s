import uuid
from typing import Iterable, List, Optional

import numpy as np
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy_utils import Ltree

from lang3s.core import config
from lang3s.core.exceptions import NotFoundException
from lang3s.data.models import (
    AnnotationOntologyMapping,
    Ontology,
    TextAnnotation,
    TopicSentences,
)
from lang3s.data.models.topic import Topic as TopicModel
from lang3s.data.schemas.topic import Topic as TopicSchema
from lang3s.data.schemas.topic import (
    TopicEntity,
    TopicFrontendResult,
    TopicSimilarSentence,
)
from lang3s.services.schemas.topics_api_schema import (
    TopicGraph,
    TopicNode,
    TopicSimilarity,
)


class TopicRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, topic_id: uuid.UUID) -> Optional[TopicSchema]:
        r = await self.session.get(TopicModel, topic_id)
        if r:
            return TopicSchema.model_validate(r)
        return None

    async def update(self, topic: TopicSchema) -> TopicSchema:
        r = await self.session.merge(TopicModel(**topic.model_dump()))
        await self.session.commit()
        return TopicSchema.model_validate(r)

    async def add(self, topic: TopicSchema) -> TopicSchema:
        topic_model = TopicModel(**topic.model_dump())
        self.session.add(topic_model)
        await self.session.commit()
        return TopicSchema.model_validate(topic_model)

    async def delete(self, topic_id: int) -> None:
        stmt = delete(TopicModel).where(TopicModel.id == topic_id)
        await self.session.execute(stmt)
        await self.session.commit()

    async def delete_in(self, topic_ids: Iterable[int]) -> None:
        for topic_id in topic_ids:
            stmt = delete(TopicModel).where(TopicModel.id == topic_id)
            await self.session.execute(stmt)
        await self.session.commit()

    async def get_support_for_topic(self, embedding: np.ndarray) -> tuple[int, int]:
        max_distance = 1.0 - config.FULL_EMBEDDING_THRESHOLD
        target_vector = embedding.tolist()
        distance_expr = TextAnnotation.embedding.cosine_distance(target_vector).label(
            "distance"
        )

        inner_stmt = (
            select(
                TextAnnotation.id,
                TextAnnotation.document_id,
                distance_expr,
            )
            .where(
                TextAnnotation.type_ == "sentence",
                TextAnnotation.metadata_json["is_stopword"].as_boolean().is_(False),
            )
            .order_by(distance_expr)
            .limit(25000)
            .subquery()
        )
        stmt = (
            select(
                func.count(inner_stmt.c.id).label("sentence_count"),
                func.count(distinct(inner_stmt.c.document_id)).label(
                    "unique_document_count"
                ),
            )
            .select_from(inner_stmt)
            .where(inner_stmt.c.distance <= max_distance)
        )
        result = await self.session.execute(stmt)
        sentence_count, document_count = result.one()
        return sentence_count, document_count

    async def delete_all(self) -> None:
        stmt = delete(TopicModel)
        await self.session.execute(stmt)
        await self.session.commit()

    async def list_topics(self) -> List[TopicSchema]:
        stmt = select(TopicModel).order_by(TopicModel.id)
        result = await self.session.scalars(stmt)
        return [TopicSchema.model_validate(t) for t in result.all()]

    async def update_topics(self, topics: List[TopicSchema]) -> None:
        with self.session.no_autoflush:
            for topic in topics:
                await self.session.merge(TopicModel(**topic.model_dump()))
        await self.session.flush()
        await self.session.commit()

    async def get_topic_info(self, topic_id: int):
        topic_m = await self.session.get(TopicModel, topic_id)
        if not topic_m:
            raise NotFoundException()
        topic = TopicSchema.model_validate(topic_m)
        stmt = (
            select(
                TopicSentences.sentence_id,
                TopicSentences.document_id,
                TopicSentences.content,
                (1.0 - TopicSentences.cosine_distance).label("similarity"),  # type: ignore
            )
            .where(TopicSentences.topic_id == topic_id)
            .order_by(TopicSentences.cosine_distance.asc())
        )
        r = await self.session.execute(stmt)
        sentences = [
            TopicSimilarSentence(
                sentence_id=sentence_id,
                document_id=document_id,
                similarity=similarity,
                content=content,
            )
            for (sentence_id, document_id, content, similarity) in r
        ]

        stmt = (
            select(
                TextAnnotation.normalized.label("entity"),
                Ontology.name.label("type"),
                func.count(TextAnnotation.id).label("count"),
            )
            .select_from(TopicSentences)
            .join(
                TextAnnotation, TopicSentences.sentence_id == TextAnnotation.sentence_id
            )
            .join(
                AnnotationOntologyMapping,
                TextAnnotation.mapping == AnnotationOntologyMapping.mapping,
            )
            .join(Ontology, Ontology.id == AnnotationOntologyMapping.ontology_id)
            .where(
                TopicSentences.topic_id == topic_id,
                Ontology.path.descendant_of(Ltree("ALL.Entity")),
            )
            .group_by(TextAnnotation.normalized, Ontology.name)
            .having(func.count(TextAnnotation.id) >= 5)
            .order_by(func.count(TextAnnotation.id).desc())
        )
        r = await self.session.execute(stmt)
        entities: list[TopicEntity] = []
        for entity, type_, count in r:
            entities.append(TopicEntity(entity=entity, type=type_, count=count))

        topic_info = TopicFrontendResult(
            sentences=sentences,
            entities=entities,
            keywords=[],
            id=topic_id,
            document_count=topic.document_count,
            sentence_count=topic.sentence_count,
            name=topic.name,
            is_fixed=topic.is_fixed,
        )
        topic_info.sentences = sentences
        return topic_info

    async def get_topic_map(self):
        def truncate(name: str) -> str:
            parts = name.split(" ")
            display = parts[0]
            for i in range(2, len(parts)):
                next_display = f"{display} {parts[i]}"
                if len(next_display) >= 44:
                    break
                display = next_display
            return f"{display}..."

        t1 = aliased(TopicModel, name="t1")
        t2 = aliased(TopicModel, name="t2")

        r = await self.session.execute(
            select(TopicModel.id, TopicModel.name, TopicModel.document_count)
        )
        nodes: list[TopicNode] = []
        for topic_id, topic_name, topic_value in r.all():
            nodes.append(
                TopicNode(
                    id=str(topic_id),
                    text=topic_name,
                    display=truncate(topic_name),
                    value=topic_value,
                )
            )

        similarity = 1 - t1.embedding.cosine_distance(t2.embedding)  # type: ignore
        stmt = (
            select(
                t1.id.label("id1"),  # type:ignore
                t2.id.label("id2"),  # type:ignore
                similarity,
            )
            .join(t2, t1.id != t2.id)  # type:ignore
            .where(similarity >= 0.7)
        )

        r = await self.session.execute(stmt)
        similarities: list[TopicSimilarity] = []
        for id1, id2, sim in r.all():
            similarities.append(
                TopicSimilarity(
                    id1=str(id1),
                    id2=str(id2),
                    similarity=sim,
                )
            )

        return TopicGraph(nodes=nodes, similarities=similarities)
