# backend/nlp/src/lang3s/db/search.py
"""
High-level semantic search utilities for Lang3s.

Builds on top of:
    - db/vector.py  (raw pgvector ops)
    - SQLAlchemy engine
    - pgvector <-> / <#> operators

Provides:
    - text search by vector
    - annotation-level vector search
    - hybrid (vector + keyword)
    - metadata-filtered searches
    - grouped results per document
    - topic assignment utilities
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Tuple

from psycopg import sql
from sqlalchemy.engine import Engine

from .vector import raw_psycopg


# ============================================================
# Helper: build safe JSONB filter clause
# ============================================================

def _metadata_filter_clause(filters: Dict[str, Any]):
    """
    Build:
        metadata ->> key = value
        metadata @> '{"key":"value"}'
    Using psycopg.sql.
    """
    clauses = []
    values = {}

    for idx, (key, val) in enumerate(filters.items()):
        key_ident = sql.Identifier("metadata")
        key_literal = sql.Literal(key)
        val_placeholder = sql.Placeholder(f"mf_{idx}")

        clause = sql.SQL("({meta} ->> {key}) = {val}").format(
            meta=sql.Identifier("metadata"),
            key=sql.Literal(key),
            val=val_placeholder,
        )

        clauses.append(clause)
        values[f"mf_{idx}"] = str(val)

    if not clauses:
        return sql.SQL("TRUE"), {}

    joined = sql.SQL(" AND ").join(clauses)
    return joined, values


# ============================================================
# Basic Text Table Search
# ============================================================

def search_texts(
    engine: Engine,
    query_vector: List[float],
    limit: int = 10,
    metadata_filters: Optional[Dict[str, Any]] = None,
    vector_op: str = "<->",  # "<->" or "<#>"
) -> List[Tuple]:
    """
    Search the text table by vector similarity.
    """
    metadata_filters = metadata_filters or {}

    mf_clause, mf_values = _metadata_filter_clause(metadata_filters)

    stmt = sql.SQL("""
                   SELECT id, text, doc_id, {vec} {op} {query} AS distance
                   FROM text
                   WHERE {mf}
                   ORDER BY distance ASC
                   LIMIT {limit}
                   """).format(
        vec=sql.Identifier("embedding"),
        op=sql.SQL(vector_op),
        query=sql.Placeholder("query"),
        limit=sql.Placeholder("limit"),
        mf=mf_clause,
    )

    params = {"query": query_vector, "limit": limit}
    params.update(mf_values)

    with raw_psycopg(engine) as conn:
        with conn.cursor() as cur:
            cur.execute(stmt, params)
            return cur.fetchall()


# ============================================================
# Document-Grouped Search
# ============================================================

def search_texts_grouped_by_document(
    engine: Engine,
    query_vector: List[float],
    per_document_limit: int = 3,
    top_documents: int = 10,
    vector_op: str = "<->",
):
    """
    Return results grouped by document:

    {
        doc_id: [
            (text_id, text, distance),
            ...
        ]
    }
    """
    stmt_docs = sql.SQL("""
                        SELECT doc_id, MIN(embedding {op} {vec}) AS best
                        FROM text
                        GROUP BY doc_id
                        ORDER BY best ASC
                        LIMIT {top}
                        """).format(
        op=sql.SQL(vector_op),
        vec=sql.Placeholder("vec"),
        top=sql.Placeholder("limit"),
    )

    with raw_psycopg(engine) as conn:
        with conn.cursor() as cur:
            cur.execute(stmt_docs, {"vec": query_vector, "limit": top_documents})
            doc_rows = cur.fetchall()

    doc_ids = [row[0] for row in doc_rows]

    if not doc_ids:
        return {}

    stmt_texts = sql.SQL("""
                         SELECT id, text, doc_id, embedding {op} {vec} AS distance
                         FROM text
                         WHERE doc_id = ANY ({doc_ids})
                         ORDER BY doc_id, distance ASC
                         """).format(
        op=sql.SQL(vector_op),
        vec=sql.Placeholder("vec"),
        doc_ids=sql.Placeholder("doc_ids"),
    )

    with raw_psycopg(engine) as conn:
        with conn.cursor() as cur:
            cur.execute(stmt_texts, {"vec": query_vector, "doc_ids": doc_ids})
            entries = cur.fetchall()

    grouped = {}
    for tid, text, doc_id, dist in entries:
        grouped.setdefault(doc_id, []).append((tid, text, dist))

    for k in grouped:
        grouped[k] = grouped[k][:per_document_limit]

    return grouped


# ============================================================
# Annotation-Level Search
# ============================================================

def search_annotations(
    engine: Engine,
    query_vector: List[float],
    limit: int = 10,
    vector_op: str = "<->",
):
    stmt = sql.SQL("""
                   SELECT id,
                          text_id,
                          doc_id,
                          type,
                          value,
                          {vec} {op} {query} AS distance
                   FROM text_annotations
                   ORDER BY distance ASC
                   LIMIT {limit}
                   """).format(
        vec=sql.Identifier("embedding"),
        op=sql.SQL(vector_op),
        query=sql.Placeholder("query"),
        limit=sql.Placeholder("limit"),
    )

    with raw_psycopg(engine) as conn:
        with conn.cursor() as cur:
            cur.execute(stmt, {"query": query_vector, "limit": limit})
            return cur.fetchall()


# ============================================================
# Hybrid Vector + Keyword Search
# ============================================================

def hybrid_text_search(
    engine: Engine,
    query_vector: List[float],
    keyword: str,
    alpha: float = 0.8,
    limit: int = 10,
):
    """
    Weighted hybrid search:
        score = alpha * vector_similarity + (1-alpha) * keyword_match_score

    Assumes keyword search uses ILIKE for simplicity.
    (Can be upgraded to PGroonga easily.)
    """
    stmt = sql.SQL("""
                   SELECT id,
                          text,
                          doc_id,
                          ({vec} <-> {query})                                               AS dist,
                          (CASE WHEN text ILIKE {kw} THEN 0 ELSE 1 END)                     AS kw_penalty,
                          (({alpha} * ({vec} <-> {query})) +
                           ((1 - {alpha}) * (CASE WHEN text ILIKE {kw} THEN 0 ELSE 1 END))) AS hybrid_score
                   FROM text
                   ORDER BY hybrid_score ASC
                   LIMIT {limit}
                   """).format(
        vec=sql.Identifier("embedding"),
        query=sql.Placeholder("query"),
        kw=sql.Placeholder("kw"),
        alpha=sql.Literal(alpha),
        limit=sql.Placeholder("limit"),
    )

    with raw_psycopg(engine) as conn:
        with conn.cursor() as cur:
            cur.execute(
                stmt,
                {"query": query_vector, "kw": f"%{keyword}%", "limit": limit}
            )
            return cur.fetchall()


# ============================================================
# Multi-Vector (Average) Search
# ============================================================

def search_multi_vector(
    engine: Engine,
    vectors: List[List[float]],
    limit: int = 10,
):
    """
    Compute centroid vector = average of vectors, then search.
    """
    if not vectors:
        return []

    dim = len(vectors[0])
    centroid = [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]

    return search_texts(engine, centroid, limit=limit)


# ============================================================
# Topic Assignment (vector-based)
# ============================================================

def assign_topics(
    engine: Engine,
    topic_table: str,
    topic_vector_col: str,
    candidate_topics: List[Tuple[str, List[float]]],
    query_vector: List[float],
    top_k: int = 3,
):
    """
    Assign text/annotation/document a topic based on vector similarity.

    candidate_topics format:
        [(topic_id, vector), ...]

    This method does not query DB, but supports memory-side routing.
    """

    def cosine(a, b):
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b + 1e-9)

    scored = [
        (topic_id, cosine(query_vector, topic_vec))
        for topic_id, topic_vec in candidate_topics
    ]

    return sorted(scored, key=lambda t: t[1], reverse=True)[:top_k]
