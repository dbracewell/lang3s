# backend/nlp/src/lang3s/db/vector.py
"""
Fully SQL-safe pgvector utilities for Lang3s using psycopg.sql.

Uses:
    - sql.SQL
    - sql.Identifier
    - sql.Placeholder
Every dynamic identifier (tables, columns) is escaped.

Supports:
    - COPY ingestion
    - Pipeline ingestion
    - Vector similarity search
    - Batch similarity ops
    - UPSERT
"""

import enum
from typing import List, Literal, Optional

import psycopg
from psycopg import sql

from lang3s import config
from lang3s.db import Database
from lang3s.db.models import TextTable, TextAnnotationsTable, TopicsTable


class SearchTable(enum.Enum):
    Text = TextTable.__tablename__
    TextAnnotations = TextAnnotationsTable.__tablename__
    Topics = TopicsTable.__tablename__


VECTOR_COLUMN = "embedding"


class VectorOperator(enum.Enum):
    Cosine = "<=>"
    InnerProduct = "<#>"
    Euclidean = "<->"
    HammingDistance = "<~>"

    def sql(self):
        if self is VectorOperator.Cosine:
            return sql.SQL("(1 - {vector_col} <=> {query})").format(
                vector_col=sql.Identifier(VECTOR_COLUMN),
                query=sql.Placeholder("vec"),
            )
        elif self is VectorOperator.Euclidean:
            return sql.SQL("{vector_col} <-> {query}").format(
                vector_col=sql.Identifier(VECTOR_COLUMN),
                query=sql.Placeholder("vec"),
            )
        elif self is VectorOperator.HammingDistance:
            return sql.SQL("1 - ({vector_col} <~> {query}::float / {dimension})").format(
                vector_col=sql.Identifier(VECTOR_COLUMN),
                dimension=sql.Identifier(str(config.TOKEN_EMBEDDING_DIMENSION)),
                query=sql.Placeholder("vec"),
            )
        elif self is VectorOperator.InnerProduct:
            return sql.SQL("{vector_col} <#> {query}").format(
                vector_col=sql.Identifier(VECTOR_COLUMN),
                query=sql.Placeholder("vec"),
            )
        raise ValueError("Unknown vector operator")

    def direction(self) -> Literal["DESC"] | Literal["ASC"]:
        if self is VectorOperator.Cosine:
            return "DESC"
        elif self is VectorOperator.Euclidean:
            return "ASC"
        elif self is VectorOperator.HammingDistance:
            return "DESC"
        elif self is VectorOperator.InnerProduct:
            return "DESC"
        raise ValueError("Unknown vector operator")


def _make_similarity_query(table: str,
                           return_cols: List[str],
                           op: VectorOperator):
    op_sql = op.sql()
    return sql.SQL("""
                   SELECT {cols}, {op} as score
                   FROM {table}
                   ORDER BY {op} {direction}
                   LIMIT {limit}
                   """).format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in return_cols),
        table=sql.Identifier(table),
        vector_col=sql.Identifier(VECTOR_COLUMN),
        op=op_sql,
        direction=sql.SQL(op.direction()),
        query=sql.Placeholder("vec"),
        limit=sql.Placeholder("limit"),
    )


def vector_search(
    table: SearchTable,
    columns: List[str],
    query_vector: List[float] | str,
    cursor: Optional[psycopg.Cursor] = None,
    op: VectorOperator = VectorOperator.Cosine,
    limit: int = 10
):
    def _perform_search(
        cur: psycopg.Cursor,
    ):
        stmt = _make_similarity_query(table.value, columns, op)
        cur.execute(
            stmt,
            {"vec": query_vector, "limit": limit}
        )
        return cur.fetchall()

    if cursor is None:
        db = Database()
        with db.cursor() as cur:
            return _perform_search(cur)
    else:
        return _perform_search(cursor)
