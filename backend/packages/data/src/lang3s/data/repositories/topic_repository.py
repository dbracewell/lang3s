import uuid
from typing import Iterable, List, Optional

import numpy as np
from sqlalchemy import Numeric, cast, delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import literal
from sqlalchemy_utils import Ltree

from lang3s.core import config
from lang3s.core.exceptions import NotFoundException
from lang3s.data.models import (
    AnnotationOntologyMapping,
    Claim,
    Document,
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
            used = 1
            for i in range(1, len(parts)):
                next_display = f"{display} {parts[i]}"
                if len(next_display) >= 44:
                    break
                display = next_display
                used += 1
            if used == len(parts):
                return display
            return f"{display}..."

        similarities: list[TopicSimilarity] = []
        topic_nodes: dict[int, TopicNode] = {}
        kw_nodes: dict[str, TopicNode] = {}

        unnested_claims = (
            select(
                Claim.document_id,
                func.unnest(Claim.keywords).label("kw"),
            )
            .distinct()
            .cte("unnested_claims")
        )
        global_stats = (
            select(func.count().label("total_docs"))
            .select_from(Document)
            .cte("global_stats")
        )
        valid_keywords = (
            select(
                unnested_claims.c.kw,
                func.count(distinct(unnested_claims.c.document_id)).label("cnt"),
            )
            .where(unnested_claims.c.kw != "")
            .group_by(unnested_claims.c.kw)
            .having(func.count() >= 10)
            .cte("valid_keywords")
        )
        doc_freq_keywords = (
            select(
                unnested_claims.c.document_id,
                unnested_claims.c.kw,
                valid_keywords.c.cnt,
            )
            .select_from(
                unnested_claims.join(
                    valid_keywords, unnested_claims.c.kw == valid_keywords.c.kw
                )
            )
            .cte("doc_freq_keywords")
        )
        k1 = doc_freq_keywords.alias("k1")
        k2 = doc_freq_keywords.alias("k2")
        topic_documents = (
            select(
                TopicSentences.topic_id,
                TopicSentences.document_id,
                TopicModel.document_count,
                TopicModel.name,
            )
            .distinct()
            .select_from(TopicSentences)
            .join(TopicModel, TopicModel.id == TopicSentences.topic_id)
            .cte("topic_documents")
        )
        r = await self.session.execute(select(topic_documents))

        for topic_id, document_id, topic_count, name in r.all():
            if topic_id not in topic_nodes:
                topic_nodes[topic_id] = TopicNode(
                    id=str(topic_id),
                    text=name,
                    display=truncate(name),
                    subvalues={},
                    type="topic",
                    value=topic_count,
                )
        stmt = (
            select(
                topic_documents.c.topic_id,
                topic_documents.c.name,
                topic_documents.c.document_count.label("topic_count"),
                doc_freq_keywords.c.kw,
                doc_freq_keywords.c.cnt.label("kw_count"),
                func.count().label("joint"),
            )
            .select_from(topic_documents)
            .join(
                doc_freq_keywords,
                doc_freq_keywords.c.document_id == topic_documents.c.document_id,
            )
            .group_by(
                topic_documents.c.topic_id,
                topic_documents.c.name,
                doc_freq_keywords.c.kw,
                doc_freq_keywords.c.cnt,
                topic_documents.c.document_count,
            )
            .having(func.count() >= 20)
        )
        r = await self.session.execute(stmt)

        for topic_id, name, topic_count, keyword, kw_count, joint_count in r.all():
            topic_nodes[topic_id].subvalues[keyword] = joint_count

            if keyword not in kw_nodes:
                kw_nodes[keyword] = TopicNode(
                    id=keyword,
                    text=keyword,
                    display=truncate(keyword),
                    subvalues={},
                    type="concept",
                    value=kw_count,
                )

            sim = joint_count / min(topic_count, kw_count)
            similarities.append(
                TopicSimilarity(
                    id1=str(topic_id),
                    id2=keyword,
                    similarity=sim,
                )
            )

        topic_model_cte = select(TopicModel.id, TopicModel.embedding).cte(
            "topic_model_cte"
        )
        t1 = aliased(topic_model_cte, name="t1")
        t2 = aliased(topic_model_cte, name="t2")
        similarity = 1 - t1.c.embedding.cosine_distance(t2.c.embedding)  # type: ignore
        stmt = (
            select(
                t1.c.id.label("id1"),  # type:ignore
                t2.c.id.label("id2"),  # type:ignore
                similarity,
            )
            .join(t2, t1.c.id != t2.c.id)  # type:ignore
            .where(similarity >= 0.7)
        )

        r = await self.session.execute(stmt)

        for id1, id2, sim in r.all():
            similarities.append(
                TopicSimilarity(
                    id1=str(id1),
                    id2=str(id2),
                    similarity=sim,
                )
            )

        paired_counts = (
            select(
                k1.c.kw.label("kw1_kw"),
                k1.c.cnt.label("kw1_cnt"),
                k2.c.kw.label("kw2_kw"),
                k2.c.cnt.label("kw2_cnt"),
                func.count().label("joint_cnt"),
            )
            .select_from(
                k1.join(
                    k2, (k1.c.document_id == k2.c.document_id) & (k1.c.kw < k2.c.kw)
                )
            )
            .group_by(k1.c.kw, k1.c.cnt, k2.c.kw, k2.c.cnt)
            .having(func.count() >= 10)
            .cte("paired_counts")
        )
        pmi_expr = func.log(
            cast(2.0, Numeric),
            (cast(paired_counts.c.joint_cnt, Numeric) * global_stats.c.total_docs)
            / (paired_counts.c.kw1_cnt * paired_counts.c.kw2_cnt),
        )
        final_query = (
            select(
                paired_counts.c.kw1_kw,
                paired_counts.c.kw1_cnt,
                paired_counts.c.kw2_kw,
                paired_counts.c.kw2_cnt,
                paired_counts.c.joint_cnt,
                pmi_expr.label("pmi_score"),
            )
            .select_from(paired_counts.join(global_stats, literal(True)))
            .where(pmi_expr > 2.0)
        )
        r = await self.session.execute(final_query)
        for kw1, kw1_cnt, kw2, kw2_count, joint_count, pmi_score in r.all():
            similarities.append(
                TopicSimilarity(
                    id1=kw1,
                    id2=kw2,
                    similarity=3 * (joint_count / min(kw1_cnt, kw2_count)),
                )
            )

        nodes = list(topic_nodes.values())
        nodes.extend(list(kw_nodes.values()))
        return TopicGraph(nodes=nodes, similarities=similarities)
