import itertools
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Dict, List

import numpy as np
import sqlalchemy as db
from numpy.typing import NDArray
from psycopg import sql
from sqlalchemy import func, select
from sqlalchemy.orm import noload

from lang3s.data.db.database import Database
from lang3s.data.db.filestore import FILE_STORE
from lang3s.data.db.models import DocumentsTable, TextAnnotationsTable
from lang3s.nlp.shared_types import (
    DOCUMENT_COLUMNS,
    TEXT_ANNOTATION_COLUMNS,
    TEXT_COLUMNS,
    Document,
)
from lang3s.services.client.redis_client import DUCKDB_QUEUE_NAME, RedisClient
from lang3s.utils.meta import SingletonMeta


def _write_doc_to_disk(doc: Document, client: RedisClient) -> None:
    doc_id = FILE_STORE.write_document(doc)
    client.enqueue(DUCKDB_QUEUE_NAME, doc_id)


class TextDatabase(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.__database = Database()

    def add_documents(self, documents: List[Document]):
        with ThreadPoolExecutor(max_workers=20) as executor:
            with RedisClient() as client:
                func = partial(_write_doc_to_disk, client=client)
                executor.map(func, documents)

        with self.__database.transaction(raw_connection=True) as cursor:
            self.__database.copy_from(
                cursor,
                "documents",
                columns=DOCUMENT_COLUMNS,
                data=(d.insert_values() for d in documents),
            )
            self.__database.copy_from(
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
            self.__database.copy_from(
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
            self.__database.copy_from(
                cursor,
                "keywords",
                columns=["document_id", "text_id", "keyword", "embedding"],
                data=keywords,
            )

    @property
    def doc_count(self):
        with self.__database.session() as session:
            return session.query(DocumentsTable).count()

    def random_sentences(self, count: int) -> List[str]:
        with self.__database.session() as session:
            annotations: List[TextAnnotationsTable] = (
                session.query(TextAnnotationsTable)
                .options(noload("*"))
                .filter(
                    TextAnnotationsTable.type_ == "sentence"
                    and TextAnnotationsTable.metadata_["is_stopword"] is False
                )
                .order_by(func.random())
                .limit(count)
                .all()
            )  # type:ignore

            return [a.text for a in annotations]  # type: ignore

    def get_documents(
        self, offset: int = 0, limit: int = 1000
    ) -> Generator[Document, None, None]:
        with self.__database.connection() as session:
            stmt = db.select(DocumentsTable.id).offset(offset).limit(limit)
            doc_ids = session.execute(stmt).fetchall()
        for record in doc_ids:
            doc_id = record[0]
            yield FILE_STORE.read_document(doc_id)

    def search_topics(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
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

        with self.__database.cursor() as cursor:
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

    def search(self, query: str, limit: int = 3) -> List[Dict[str, str]]:
        query = " OR ".join(query.split())
        sql_query = sql.SQL("""
                            WITH search_results AS (SELECT distinct text,
                                                                    doc_id,
                                                                    pgroonga_score(tableoid,ctid) as rank
                                                    FROM text_annotations
                            WHERE type = 'sentence'
                              and text &@~ (%s, ARRAY [1], ARRAY ['scorer_tf_idf($index)'], 'ml_text_annotation_search_index')::pgroonga_full_text_search_condition_with_scorers
                            )
                            SELECT text, title, doc_id, rank
                            FROM search_results
                            INNER JOIN documents ON documents.id = doc_id
                            ORDER BY rank desc
                            LIMIT %s
                            """)

        with self.__database.cursor() as cursor:
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

    def sentence_search(
        self, embedding: NDArray[np.floating], min_similarity: float, limit: int = 3
    ) -> List[str]:
        stmt = (
            select(TextAnnotationsTable)
            .filter(
                (1 - TextAnnotationsTable.embedding.cosine_distance(embedding))
                >= min_similarity
            )
            .limit(limit)
        )

        with self.__database.session() as session:
            results = session.scalars(stmt).all()
            return [r.content for r in results]
