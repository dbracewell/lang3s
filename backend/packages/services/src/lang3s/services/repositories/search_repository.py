import re
from typing import Literal

import numpy as np
from cachetools import TTLCache, cached
from sqlalchemy import func, literal, not_, select, text, union_all
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.exceptions import BadDataException
from lang3s.data.models import (
    AnnotationOntologyMapping,
    Document,
    Ontology,
    TextAnnotation,
    Topic,
    TopicSentences,
)
from lang3s.nlp import Embedder
from lang3s.services.schemas.search_api_schema import (
    AnnotationDocResult,
    AnnotationHighlight,
    AnnotationSearchResult,
    AnnotationSearchResults,
    DocumentHighlight,
    DocumentSearchResult,
    DocumentSearchResults,
    EffectiveSearchParams,
    HumanizedQuery,
    SearchParams,
    TopicDocSearchResult,
    TopicHighlight,
    TopicSearchResult,
    TopicSearchResults,
)

SEARCH_DOCUMENT_CASED_THRESHOLD = 0.5
SEARCH_DOCUMENT_UNCASED_THRESHOLD = 0.3
SEARCH_TOPIC_CASED_THRESHOLD = 0.65
SEARCH_TOPIC_UNCASED_THRESHOLD = 0.3
SEARCH_ANNOTATION_CASED_THRESHOLD = 0.65
SEARCH_ANNOTATION_UNCASED_THRESHOLD = 0.35


def create_full_text_search(
    query: str | None,
    is_annotation_search: bool = True,
):
    full_text_rank = func.dense_rank().over(
        order_by=func.pgroonga_score(text("tableoid"), text("ctid")).desc()
    )
    type_filter = (
        TextAnnotation.type_ != "sentence"
        if is_annotation_search
        else TextAnnotation.type_ == "sentence"
    )

    snippet_text = (
        TextAnnotation.normalized if is_annotation_search else TextAnnotation.content
    )

    cleanQuery = (query or "").replace(" OR ", " ")
    snippet_expr = func.array_to_string(
        func.pgroonga_snippet_html(
            snippet_text,
            func.pgroonga_query_extract_keywords(cleanQuery),
        ),
        "\n",
    )

    base = (
        select(
            TextAnnotation.id,
            TextAnnotation.document_id,
            TextAnnotation.sentence_id,
            TextAnnotation.sentence_index,
            TextAnnotation.mapping,
            TextAnnotation.normalized.label("annotation"),
            snippet_expr.label("snippet"),
            full_text_rank.label("item_rank"),
            full_text_rank.label("score_rank"),
            literal(2).label("priority"),
        )
        .distinct()
        .select_from(TextAnnotation)
        .where(
            not_(TextAnnotation.is_stopword),
            type_filter,
            snippet_text.op("&@~")(query),
        )
    )

    if is_annotation_search:
        base = base.subquery("ft_base")
        return (
            select(base, Ontology.path)
            .join(
                AnnotationOntologyMapping,
                base.c.mapping == AnnotationOntologyMapping.mapping,
            )
            .join(Ontology, Ontology.id == AnnotationOntologyMapping.ontology_id)
        )

    return base


def create_semantic_search(
    query: np.ndarray | None,
    threshold: float,
    is_annotation_search: bool = True,
):
    distance = TextAnnotation.embedding.cosine_distance(query)
    type_filter = (
        TextAnnotation.type_ != "sentence"
        if is_annotation_search
        else TextAnnotation.type_ == "sentence"
    )
    rank = func.dense_rank().over(order_by=(1 - distance).desc())

    base = (
        select(
            TextAnnotation.id,
            TextAnnotation.document_id,
            TextAnnotation.sentence_id,
            TextAnnotation.sentence_index,
            TextAnnotation.mapping,
            TextAnnotation.normalized.label("annotation"),
            TextAnnotation.content.label("snippet"),
            rank.label("item_rank"),
            rank.label("score_rank"),
            literal(1).label("priority"),
        )
        .distinct()
        .select_from(TextAnnotation)
        .where(
            not_(TextAnnotation.is_stopword),
            type_filter,
            (1 - distance) >= threshold,
        )
    )

    if is_annotation_search:
        base = base.subquery("ft_base")
        return (
            select(base, Ontology.path)
            .join(
                AnnotationOntologyMapping,
                base.c.mapping == AnnotationOntologyMapping.mapping,
            )
            .join(Ontology, Ontology.id == AnnotationOntologyMapping.ontology_id)
        )

    return base


def _create_unique_rows(
    query: EffectiveSearchParams,
    full_text_search,
    semantic_search,
    is_annotation_search: bool = False,
):
    if query.q and query.embedding is not None:
        union_query = union_all(full_text_search, semantic_search).subquery()

        if query.is_strict:
            combined_statement = (
                select(union_query)
                .add_columns(literal(1).label("row_rank"))
                .where(union_query.c.priority == 2)
                .subquery()
            )
        else:
            combined_statement = (
                select(union_query)
                .add_columns(
                    func.row_number()
                    .over(
                        partition_by=union_query.c.annotation
                        if is_annotation_search
                        else union_query.c.sentence_id,
                        order_by=union_query.c.priority.desc(),
                    )
                    .label("row_rank")
                )
                .subquery()
            )

        item_rrf = (1.0 / (60.0 + combined_statement.c.item_rank)).label("item_rank")
        score_rrf = (1.0 / (60.0 + combined_statement.c.score_rank)).label("score_rank")

        columns = [
            c
            for c in combined_statement.c  # type:ignore
            if c.name not in ("item_rank", "score_rank")
        ]

        return (
            select(
                *columns,
                item_rrf,
                score_rrf,
            )
            .where(combined_statement.c.row_rank == 1)
            .order_by(score_rrf.desc())
            .subquery("unique_rows")
        )

    elif query.q:
        return full_text_search.subquery("combined_results")
    elif query.embedding is not None:
        return semantic_search.subquery("combined_results")

    raise BadDataException()


class SearchRepository:
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    def _base_query(
        self,
        query: EffectiveSearchParams,
        threshold: float,
        is_annotation_search: bool,
    ):
        full_text_search = create_full_text_search(
            query.q,
            is_annotation_search=is_annotation_search,
        )
        semantic_search = create_semantic_search(
            query=query.embedding,
            threshold=threshold,
            is_annotation_search=is_annotation_search,
        )
        return _create_unique_rows(
            query=query,
            full_text_search=full_text_search,
            semantic_search=semantic_search,
            is_annotation_search=is_annotation_search,
        )

    async def search_documents(self, query: SearchParams) -> DocumentSearchResults:
        query: EffectiveSearchParams = await self._prepare_params(query)
        threshold = (
            SEARCH_DOCUMENT_CASED_THRESHOLD
            if query.has_case
            else SEARCH_DOCUMENT_UNCASED_THRESHOLD
        )
        unique_rows = self._base_query(
            query=query,
            threshold=threshold,
            is_annotation_search=False,
        )

        final_ordering = (
            select(
                unique_rows.c.document_id,
                Document.title,
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            literal("text"),
                            unique_rows.c.snippet,
                            literal("sentence_id"),
                            unique_rows.c.sentence_id,
                        ),
                        unique_rows.c.sentence_index.asc(),
                    )
                ).label("highlights"),
                func.sum(unique_rows.c.item_rank).label("item_rank"),
            )
            .select_from(unique_rows)
            .join(Document, Document.id == unique_rows.c.document_id)
            .group_by(
                unique_rows.c.document_id,
                Document.title,
            )
            .order_by(func.sum(unique_rows.c.item_rank).desc())
        ).subquery("final_ordering")

        total_stmt = select(func.count()).select_from(final_ordering)
        total_results = 0
        if query.cursor == 1:
            total_results = await self.session.scalar(total_stmt) or 0

        results: list[DocumentSearchResult] = []

        r = await self.session.execute(
            select(final_ordering).offset(query.offset).limit(query.limit + 1)
        )
        for document_id, title, content, ir in r.all():
            results.append(
                DocumentSearchResult(
                    document_id=document_id,
                    document_title=title,
                    highlights=[
                        DocumentHighlight(
                            text=c.get("text"),
                            document_id=document_id,
                            sentence_id=c.get("sentence_id"),
                        )
                        for c in content
                    ],
                )
            )

        next_cursor, results = query.generate_page(results)
        return DocumentSearchResults(
            total=total_results,
            results=results,
            next_cursor=next_cursor,
        )

    async def search_topics(self, query: SearchParams) -> TopicSearchResults:
        query: EffectiveSearchParams = await self._prepare_params(query)
        threshold = (
            SEARCH_TOPIC_CASED_THRESHOLD
            if query.has_case
            else SEARCH_TOPIC_UNCASED_THRESHOLD
        )
        unique_rows = self._base_query(
            query=query,
            threshold=threshold,
            is_annotation_search=False,
        )

        final_ordering = (
            select(
                TopicSentences.topic_id.label("id"),
                Topic.name,
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            literal("text"),
                            unique_rows.c.snippet,
                            literal("document_id"),
                            unique_rows.c.document_id,
                            literal("document_title"),
                            Document.title,
                            literal("sentence_id"),
                            unique_rows.c.sentence_id,
                        ),
                        unique_rows.c.item_rank.desc(),
                        unique_rows.c.document_id.asc(),
                        unique_rows.c.sentence_index.asc(),
                    )
                ),
            )
            .select_from(TopicSentences)
            .join(unique_rows, unique_rows.c.sentence_id == TopicSentences.sentence_id)
            .join(Topic, Topic.id == TopicSentences.topic_id)
            .join(Document, Document.id == TopicSentences.document_id)
            .group_by(
                TopicSentences.topic_id,
                Topic.name,
            )
            .order_by(func.max(unique_rows.c.item_rank).desc())
            .subquery("final_ordering")
        )

        total_results = 0
        if query.cursor == 1:
            total_results = (
                await self.session.scalar(
                    select(func.count()).select_from(final_ordering)
                )
                or 0
            )

        with_text = select(final_ordering).offset(query.offset).limit(query.limit + 1)
        results: list[TopicSearchResult] = []
        r = await self.session.execute(with_text)
        for topic_id, name, content in r.all():
            by_doc = {}
            for h in content:
                doc_id = h.get("document_id")
                if doc_id not in by_doc:
                    by_doc[doc_id] = TopicDocSearchResult(
                        document_id=doc_id,
                        document_title=h.get("document_title"),
                        highlights=[],
                    )
                by_doc[doc_id].highlights.append(
                    TopicHighlight(
                        sentence_id=h.get("sentence_id"),
                        text=h.get("text"),
                    )
                )
            results.append(
                TopicSearchResult(
                    id=topic_id,
                    name=name,
                    docs=list(by_doc.values()),
                )
            )

        next_cursor, results = query.generate_page(results)
        return TopicSearchResults(
            total=total_results,
            results=results,
            next_cursor=next_cursor,
        )

    async def search_annotations(self, query: SearchParams) -> AnnotationSearchResults:
        query = await self._prepare_params(query)
        threshold = (
            SEARCH_ANNOTATION_CASED_THRESHOLD
            if query.has_case
            else SEARCH_ANNOTATION_UNCASED_THRESHOLD
        )
        unique_rows = self._base_query(
            query=query,
            threshold=threshold,
            is_annotation_search=True,
        )

        final_ordering = (
            select(
                unique_rows.c.annotation,
                unique_rows.c.path,
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            "id",
                            unique_rows.c.id,
                            "snippet",
                            unique_rows.c.snippet,
                            "document_id",
                            unique_rows.c.document_id,
                            "sentence_id",
                            unique_rows.c.sentence_id,
                            "sentence",
                            TextAnnotation.content,
                        ),
                        unique_rows.c.document_id.asc(),
                        unique_rows.c.sentence_index.asc(),
                    )
                ).label("highlights"),
                func.sum(unique_rows.c.score_rank).label("score_rank"),
            )
            .select_from(unique_rows)
            .join(TextAnnotation, TextAnnotation.id == unique_rows.c.sentence_id)
            .group_by(unique_rows.c.annotation, unique_rows.c.path)
            .subquery()
        )

        total_results = 0
        if query.cursor == 1:
            total_results = (
                await self.session.scalar(
                    select(func.count()).select_from(final_ordering)
                )
                or 0
            )

        r = await self.session.execute(
            select(final_ordering)
            .order_by(
                final_ordering.c.score_rank.desc(), final_ordering.c.annotation.asc()
            )
            .offset(query.offset)
            .limit(query.limit + 1)
        )

        results: list[AnnotationSearchResult] = []
        for normalized, path, highlights, sr in r.all():
            by_doc = {}
            for h in highlights:
                doc_id = h.get("document_id")
                if doc_id not in by_doc:
                    by_doc[doc_id] = AnnotationDocResult(
                        document_id=doc_id,
                        document_title=doc_id,
                        highlights=[],
                    )
                by_doc[doc_id].highlights.append(
                    AnnotationHighlight(
                        id=h.get("id"),
                        sentence_id=h.get("sentence_id"),
                        annotation=h.get("snippet"),
                        sentence=h.get("sentence"),
                    )
                )
            results.append(
                AnnotationSearchResult(
                    name=normalized,
                    path=path.path,
                    docs=list(by_doc.values()),
                )
            )

        next_cursor, results = query.generate_page(results)
        return AnnotationSearchResults(
            total=total_results,
            results=results,
            next_cursor=next_cursor,
        )

    async def humanize_query(self, query: SearchParams) -> HumanizedQuery:
        annotations = []
        for aid in query.aid or []:
            a: TextAnnotation = await self._get_annotation(aid)
            if a:
                annotations.append(a.normalized)
        topics = []
        for tid in query.tid or []:
            a: Topic = await self._get_topic(tid)
            if a:
                topics.append(a.name)

        return HumanizedQuery(annotations=annotations, topics=topics)

    @cached(cache=TTLCache(maxsize=1000, ttl=3600))
    async def _get_annotation(self, annotation_id: str) -> TextAnnotation | None:
        return await self.session.get(TextAnnotation, annotation_id)

    @cached(cache=TTLCache(maxsize=1000, ttl=3600))
    async def _get_topic(self, topic_id: int) -> Topic | None:
        return await self.session.get(Topic, topic_id)

    @cached(cache=TTLCache(maxsize=1000, ttl=3600))
    def _embed_query(self, query: str) -> tuple[bool, list[np.ndarray]]:
        embedder = Embedder()
        query_strings = re.split(
            r" (OR|or) ", re.sub(r"\s+", " ", query.replace('"', " "))
        )
        task: Literal["nli", "search"] = "nli"
        has_case = True
        if all(q == q.upper() or q == q.lower() for q in query_strings):
            task = "search"
            has_case = False
        return has_case, embedder(query_strings, task=task).sentence_embeddings

    async def _prepare_params(self, query: SearchParams) -> EffectiveSearchParams:
        embedding: list[np.ndarray] = []
        for aid in query.aid or []:
            a = await self._get_annotation(aid)
            if a:
                embedding.append(a.embedding.to_numpy())
        for tid in query.tid or []:
            t = await self._get_topic(tid)
            if t:
                embedding.append(t.embedding.to_numpy())

        is_strict = query.is_strict or False
        has_case = True
        if query.q and len(embedding) == 0 and not is_strict:
            has_case, query_embedding = self._embed_query(query.q)
            embedding.extend(query_embedding)

        effective_embedding = None
        if len(embedding) > 0:
            effective_embedding = np.average(embedding, axis=0)
        return EffectiveSearchParams(
            cursor=max(query.cursor or 1, 1),
            limit=query.limit,
            is_strict=is_strict,
            embedding=effective_embedding,
            q=query.q.strip() if query.q and query.q.strip() else None,
            has_case=has_case,
        )
