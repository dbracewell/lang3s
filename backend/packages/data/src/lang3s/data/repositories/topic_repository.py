import uuid
from typing import Iterable, List, Optional

import numpy as np
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core import config
from lang3s.data.models import TextAnnotation
from lang3s.data.models.topic import Topic as TopicModel
from lang3s.data.schemas.topic import Topic as TopicSchema


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
