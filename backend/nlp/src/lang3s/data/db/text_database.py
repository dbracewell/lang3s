import itertools
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Dict, List

import numpy as np
from numpy.typing import NDArray
from psycopg import sql
from sqlalchemy import Boolean, Select, cast, func, select

import lang3s.data.db.database as db
from lang3s.data.db.models import DocumentsTable, TextAnnotationsTable
from lang3s.data.filestore import FILE_STORE
from lang3s.nlp.shared_types import (
    DOCUMENT_COLUMNS,
    TEXT_ANNOTATION_COLUMNS,
    TEXT_COLUMNS,
    Document,
)
from lang3s.services.client.redis_client import DUCKDB_QUEUE_NAME, RedisClient


def _write_doc_to_disk(doc: Document, client: RedisClient) -> None:
    doc_id = FILE_STORE.write_document(doc)
    client.enqueue(DUCKDB_QUEUE_NAME, doc_id)


def add_documents(documents: List[Document]):
    with ThreadPoolExecutor(max_workers=20) as executor:
        with RedisClient() as client:
            executor.map(partial(_write_doc_to_disk, client=client), documents)

    with db.transaction(raw=True) as cursor:
        db.copy_from(
            cursor,
            "documents",
            columns=DOCUMENT_COLUMNS,
            data=(d.insert_values() for d in documents),
        )
        db.copy_from(
            cursor,
            "text",
            columns=TEXT_COLUMNS,
            data=(d.text.insert_values() for d in documents),
        )
        all_annotations = itertools.chain.from_iterable(
            (doc.text.all_annotations for doc in documents if doc.text is not None)
        )
        filtered_annotations = (
            a.insert_values() for a in all_annotations if a.type != "token"
        )
        db.copy_from(
            cursor,
            "text_annotations",
            columns=TEXT_ANNOTATION_COLUMNS,
            data=filtered_annotations,
        )
        keywords = (
            [doc.id, doc.text.id, keyword, embedding]
            for doc in documents
            if doc.text is not None
            for keyword, embedding in doc.text.keywords
        )
        db.copy_from(
            cursor,
            "keywords",
            columns=["document_id", "text_id", "keyword", "embedding"],
            data=keywords,
        )


def document_count(self):
    with db.get_session() as session:
        return session.query(DocumentsTable).count()


def random_sentences(count: int, include_embedding=False) -> List[dict[str, str]]:
    with db.get_session() as session:
        stmt = (
            select(
                TextAnnotationsTable.content,
                TextAnnotationsTable.embedding,
                DocumentsTable.id,
                DocumentsTable.title,
            )
            .join(DocumentsTable, TextAnnotationsTable.documentId == DocumentsTable.id)
            .where(
                TextAnnotationsTable.type_ == "sentence",
                cast(TextAnnotationsTable.metadata_["is_stopword"], Boolean) == False,
            )
            .order_by(func.random())
            .limit(count)
        )
        return_sentences = []

        for content, embedding, document_id, document_title in session.execute(
            stmt
        ).all():
            sentence_obj = {
                "document_id": document_id,
                "title": document_title,
                "content": content,
            }
            if include_embedding:
                sentence_obj["embedding"] = embedding.to_numpy()
            return_sentences.append(sentence_obj)

        return return_sentences


def get_documents(
    last_id: str | None = None,
    limit: int = 100,
) -> Generator[Document, None, None]:
    last_doc_id = last_id
    with db.get_session() as session:
        while True:
            stmt = select(DocumentsTable.id).order_by(DocumentsTable.id)

            if last_doc_id is not None:
                stmt = stmt.where(DocumentsTable.id > last_doc_id)

            stmt = stmt.limit(limit)
            docs = session.execute(stmt).scalars().all()
            if not docs:
                break

            for doc_id in docs:
                last_doc_id = doc_id
                yield FILE_STORE.read_document(doc_id)


def fts_topic_search(query: str, limit: int = 3) -> List[Dict[str, str]]:
    query = " OR ".join(query.split())
    sql_query = sql.SQL("""
                    WITH search_results AS (SELECT distinct sentence_aid,
                                                            text,
                                                            pgroonga_score(tableoid,ctid) as rank
                                            FROM text_annotations
                    WHERE type = 'sentence'
                      and text &@~ (%s, ARRAY [1], ARRAY ['scorer_tf_idf($index)'], 'ml_text_annotation_search_index')::pgroonga_full_text_search_condition_with_scorers
                    )
                    SELECT text, title, name as topic, topic_id, doc_id, rank
                    FROM search_results
                    INNER JOIN topic_sentences ON topic_sentences.sentence_aid = search_results.sentence_aid
                        INNER JOIN documents ON documents.id = topic_sentences.doc_id
                        INNER JOIN topics ON topics.id = topic_sentences.topic_id
                    ORDER BY rank desc
                    LIMIT %s
                    """)

    with db.raw_cursor() as cursor:
        cursor.execute(sql_query, (query, limit))
        result = cursor.fetchall()
        return [
            {
                "content": sentence[0],
                "title": sentence[1],
                "topic": sentence[2],
                "topicId": sentence[3],
                "documentId": sentence[4],
            }
            for sentence in result
        ]


def fts_sentence_search(query: str, limit: int = 3) -> List[Dict[str, str]]:
    query = " OR ".join(query.split())
    sql_query = sql.SQL("""
                        WITH search_results AS (SELECT distinct text,
                                                                doc_id,
                                                                pgroonga_score(tableoid,ctid) as rank
                                                FROM text_annotations
                        WHERE type = 'sentence'
                            and metadata->>'is_stopword' = 'false'
                          and text &@~ (%s, ARRAY [1], ARRAY ['scorer_tf_idf($index)'], 'ml_text_annotation_search_index')::pgroonga_full_text_search_condition_with_scorers
                        )
                        SELECT text, title, doc_id, rank
                        FROM search_results
                        INNER JOIN documents ON documents.id = doc_id
                        ORDER BY rank desc
                        LIMIT %s
                        """)

    with db.raw_cursor() as cursor:
        cursor.execute(sql_query, (query, limit))
        result = cursor.fetchall()
        return [
            {
                "content": sentence[0],
                "title": sentence[1],
                "documentId": str(sentence[2]),
            }
            for sentence in result
        ]


def semantic_sentence_search(
    embedding: NDArray[np.floating], min_similarity: float, limit: int = 3
) -> List[str]:
    stmt = (
        select(TextAnnotationsTable.content)
        .where(
            (
                (1 - TextAnnotationsTable.embedding.cosine_distance(embedding))
                >= min_similarity
            )
            & (TextAnnotationsTable.metadata_["is_stopword"].astext == "false")
        )
        .limit(limit)
    )

    with db.get_session() as session:
        results = session.scalars(stmt).all()
        return [r for r in results]
