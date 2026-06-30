import threading

import numpy as np
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
from lang3s.services.schemas.search_api_schema import (
    AnnotationDocResult,
    AnnotationHighlight,
    AnnotationSearchResult,
    AnnotationSearchResults,
    DocumentSearchResult,
    DocumentSearchResults,
    EffectiveSearchParams,
    Highlight,
    SearchParams,
    TopicSearchResult,
    TopicSearchResults,
)

full_text_rank = func.dense_rank().over(
    order_by=func.pgroonga_score(text("tableoid"), text("ctid")).desc()
)


def semantic_rank(distance, agg=False):
    if agg:
        return func.dense_rank().over(order_by=func.min(distance).asc())
    return func.dense_rank().over(order_by=distance.asc())


def full_text_sentence_search(query: str | None):
    cleanQuery = (query or "").replace(" OR ", " ")
    snippet_expr = func.array_to_string(
        func.pgroonga_snippet_html(
            TextAnnotation.content,
            func.pgroonga_query_extract_keywords(cleanQuery),
        ),
        "\n",
    )
    return select(
        TextAnnotation.document_id,
        TextAnnotation.sentence_id,
        TextAnnotation.sentence_index,
        snippet_expr.label("snippet"),
        full_text_rank.label("item_rank"),
        full_text_rank.label("score_rank"),
    ).where(
        not_(TextAnnotation.is_stopword),
        TextAnnotation.type_ == "sentence",
        TextAnnotation.content.op("&@~")(query),
    )


def full_text_annotation_search(query: str | None):
    cleanQuery = (query or "").replace(" OR ", " ")
    snippet_expr = func.array_to_string(
        func.pgroonga_snippet_html(
            TextAnnotation.content,
            func.pgroonga_query_extract_keywords(cleanQuery),
        ),
        "\n",
    )
    return select(
        TextAnnotation.id,
        TextAnnotation.document_id,
        TextAnnotation.sentence_id,
        TextAnnotation.sentence_index,
        TextAnnotation.mapping,
        TextAnnotation.normalized.label("annotation"),
        snippet_expr.label("snippet"),
        full_text_rank.label("item_rank"),
        full_text_rank.label("score_rank"),
    ).where(
        not_(TextAnnotation.is_stopword),
        TextAnnotation.type_ != "sentence",
        TextAnnotation.normalized.op("&@~")(query),
    )


def semantic_annotation_search(query: np.ndarray | None, threshold: float):
    distance = TextAnnotation.embedding.cosine_distance(query)
    return (
        select(
            TextAnnotation.id,
            TextAnnotation.document_id,
            TextAnnotation.sentence_id,
            TextAnnotation.sentence_index,
            TextAnnotation.mapping,
            TextAnnotation.normalized.label("annotation"),
            TextAnnotation.normalized.label("snippet"),
            semantic_rank(distance).label("item_rank"),
            semantic_rank(distance).label("score_rank"),
        )
        .select_from(TextAnnotation)
        .where(
            not_(TextAnnotation.is_stopword),
            TextAnnotation.type_ != "sentence",
            distance <= threshold,
        )
    )


def semantic_sentence_search(query: np.ndarray | None, threshold: float):
    distance = TextAnnotation.embedding.cosine_distance(query)
    return (
        select(
            TextAnnotation.document_id,
            TextAnnotation.sentence_id,
            TextAnnotation.sentence_index,
            TextAnnotation.content.label("snippet"),
            semantic_rank(distance).label("item_rank"),
            semantic_rank(distance).label("score_rank"),
        )
        .select_from(TextAnnotation)
        .where(
            not_(TextAnnotation.is_stopword),
            TextAnnotation.type_ == "sentence",
            distance <= threshold,
        )
    )


def _create_unique_rows(
    query: EffectiveSearchParams,
    full_text_search,
    semantic_search,
    is_annotation_search=False,
):
    if query.q and query.embedding is not None:
        combined_statement = union_all(full_text_search, semantic_search).subquery(
            "combined_results"
        )

        if is_annotation_search:
            longest_text = (
                select(
                    combined_statement.c.id,
                    func.max(func.length(combined_statement.c.snippet)).label(
                        "max_snippet"
                    ),
                )
                .select_from(combined_statement)
                .group_by(combined_statement.c.id)
            )

        else:
            longest_text = (
                select(
                    combined_statement.c.sentence_id,
                    func.max(func.length(combined_statement.c.snippet)).label(
                        "max_snippet"
                    ),
                )
                .select_from(combined_statement)
                .group_by(combined_statement.c.sentence_id)
            )

        if query.is_strict:
            longest_text = longest_text.where(
                combined_statement.c.snippet.contains("<span class=")
            )

        longest_text = longest_text.group_by(combined_statement.c.sentence_id).subquery(
            "max_snippet"
        )
        item_rrf = func.sum(1.0 / (60.0 + combined_statement.c.item_rank)).label(
            "item_rank"
        )
        score_rrf = func.sum(1.0 / (60.0 + combined_statement.c.score_rank)).label(
            "score_rank"
        )

        columns = [
            c for c in combined_statement.c if c.name not in ("item_rank", "score_rank")
        ]
        return (
            select(
                *columns,
                item_rrf,
                score_rrf,
            )
            .join(
                longest_text,
                (longest_text.c.id == combined_statement.c.id)
                if is_annotation_search
                else (longest_text.c.sentence_id == combined_statement.c.sentence_id)
                & (
                    longest_text.c.max_snippet
                    == func.length(combined_statement.c.snippet)
                ),
            )
            .group_by(
                *columns,
            )
            .order_by(score_rrf.desc())
            .subquery("unique_rows")
        )

    elif query.q:
        return full_text_search.subquery("combined_results")
    elif query.embedding:
        return semantic_search.subquery("combined_results")

    raise BadDataException()


class SearchRepository:
    def __init__(self):
        self.session: AsyncSession | None = None
        self.threshold = 0.34

    async def search_documents(self, query: SearchParams) -> DocumentSearchResults:
        query: EffectiveSearchParams = await self._prepare_params(query)
        full_text_search = full_text_sentence_search(query.q)
        semantic_search = semantic_sentence_search(query.embedding, self.threshold)

        unique_rows = _create_unique_rows(
            query,
            full_text_search,
            semantic_search,
        )

        final_result = (
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
                func.min(unique_rows.c.item_rank).label("item_rank"),
            )
            .select_from(unique_rows)
            .join(Document, Document.id == unique_rows.c.document_id)
            .group_by(
                unique_rows.c.document_id,
                Document.title,
            )
        )

        total_stmt = select(func.count()).select_from(final_result.subquery("count"))
        total_results = 0
        if query.cursor == 1:
            total_results = await self.session.scalar(total_stmt) or 0

        results: list[DocumentSearchResult] = []
        r = await self.session.execute(
            final_result.offset(query.offset).limit(query.limit + 1)
        )
        for document_id, title, content, ir in r.all():
            results.append(
                DocumentSearchResult(
                    document_id=document_id,
                    document_title=title,
                    highlights=[
                        Highlight(
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

        full_text_search = full_text_sentence_search(query.q)
        semantic_search = semantic_sentence_search(query.embedding, self.threshold)
        unique_rows = _create_unique_rows(
            query,
            full_text_search,
            semantic_search,
        )

        with_text = (
            select(
                TopicSentences.topic_id.label("id"),
                Topic.name,
                func.json_agg(
                    aggregate_order_by(
                        func.json_build_object(
                            literal("text"),
                            unique_rows.c.snippet,
                            literal("rank"),
                            unique_rows.c.item_rank,
                            literal("document_id"),
                            unique_rows.c.document_id,
                            literal("sentence_id"),
                            unique_rows.c.sentence_id,
                        ),
                        unique_rows.c.document_id.asc(),
                        unique_rows.c.sentence_index.asc(),
                    )
                ),
            )
            .select_from(TopicSentences)
            .join(unique_rows, unique_rows.c.sentence_id == TopicSentences.sentence_id)
            .join(Topic, Topic.id == TopicSentences.topic_id)
            .group_by(
                TopicSentences.topic_id,
                Topic.name,
            )
        )

        total_results = 0
        if query.cursor == 1:
            total_results = (
                await self.session.scalar(
                    select(func.count()).select_from(with_text.subquery("with_text"))
                )
                or 0
            )

        with_text = with_text.offset(query.offset).limit(query.limit + 1)
        results: list[TopicSearchResult] = []
        r = await self.session.execute(with_text)
        for topic_id, name, content in r.all():
            results.append(
                TopicSearchResult(
                    id=topic_id,
                    name=name,
                    highlights=[
                        Highlight(
                            text=c.get("text"),
                            document_id=c.get("document_id"),
                            sentence_id=c.get("sentence_id"),
                        )
                        for c in content
                    ],
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
        full_text_search = full_text_annotation_search(query.q)
        semantic_search = semantic_annotation_search(query.embedding, self.threshold)
        unique_rows = _create_unique_rows(
            query,
            full_text_search,
            semantic_search,
            is_annotation_search=True,
        )

        final_stmt = (
            select(
                unique_rows.c.annotation,
                Ontology.path,
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
                func.min(unique_rows.c.score_rank).label("score_rank"),
            )
            .select_from(unique_rows)
            .join(TextAnnotation, TextAnnotation.id == unique_rows.c.sentence_id)
            .join(
                AnnotationOntologyMapping,
                AnnotationOntologyMapping.mapping == unique_rows.c.mapping,
            )
            .join(Ontology, Ontology.id == AnnotationOntologyMapping.ontology_id)
            .group_by(unique_rows.c.annotation, Ontology.path)
            .order_by(func.min(unique_rows.c.score_rank).desc())
        )

        total_results = 0
        if query.cursor == 1:
            total_results = (
                await self.session.scalar(
                    select(func.count()).select_from(final_stmt.subquery("final_stmt"))
                )
                or 0
            )

        r = await self.session.execute(
            select(final_stmt.subquery("final_stmt"))
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

    # @cached(cache=TTLCache(maxsize=100, ttl=3600))
    async def _annotation_embeddings(
        self,
        annotation_ids: list[str],
    ) -> list[np.ndarray]:
        embedding: list[np.ndarray] = []
        for annotation in annotation_ids:
            a = await self.session.get(TextAnnotation, annotation)  # type: ignore
            if a:
                embedding.append(a.embedding.to_numpy())
        return embedding

    # @cached(cache=TTLCache(maxsize=100, ttl=3600))
    async def _topic_embeddings(self, topic_ids: list[int]) -> list[np.ndarray]:
        embedding: list[np.ndarray] = []
        for topic_id in topic_ids:
            a = await self.session.get(Topic, topic_id)  # type: ignore
            if a:
                embedding.append(a.embedding.to_numpy())
        return embedding

    # @cached(cache=TTLCache(maxsize=100, ttl=3600))
    async def _prepare_params(self, query: SearchParams) -> EffectiveSearchParams:
        embedding: list[np.ndarray] = []
        if query.aid:
            embedding.extend(await self._annotation_embeddings(query.aid))
        if query.tid:
            embedding.extend(await self._topic_embeddings(query.tid))

        effective_embedding = None
        if len(embedding) > 0:
            effective_embedding = np.average(embedding, axis=0)
        return EffectiveSearchParams(
            cursor=max(query.cursor or 1, 1),
            limit=query.limit,
            is_strict=query.is_strict or False,
            embedding=effective_embedding,
            q=query.q.strip() if query.q and query.q.strip() else None,
        )


_instance: SearchRepository | None = None
_lock = threading.Lock()


def get_instance(session: AsyncSession) -> SearchRepository:
    global _instance
    _lock.acquire()
    try:
        if _instance is None:
            _instance = SearchRepository()
        _instance.session = session
        return _instance  # type:ignore
    except Exception:
        raise
    finally:
        _lock.release()
