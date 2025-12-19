import gzip
import itertools
import json
import os
from collections.abc import Generator
from threading import Thread
from typing import Iterable, List

import numpy as np
import sqlalchemy as db
from numpy.typing import NDArray
from psycopg import sql
from sqlalchemy import func
from sqlalchemy.orm import noload

from lang3s import config
from lang3s.db.database import Database
from lang3s.db.models import DocumentsTable, TextAnnotationsTable
from lang3s.maths import binarize
from lang3s.shared_types import DOCUMENT_COLUMNS, TEXT_ANNOTATION_COLUMNS, TEXT_COLUMNS, Document
from lang3s.utils.meta import SingletonMeta


def _write_docs_to_disk(documents: Iterable[Document]):
    documents_dir = config.DOCUMENTS_DIR
    os.makedirs(documents_dir, exist_ok=True)

    for doc in documents:
        doc_path = os.path.join(documents_dir, f"{doc.id}.json")
        with gzip.open(doc_path + ".gz", "wt", encoding="utf-8") as gzip_fp:
            json.dump(doc.to_json(), gzip_fp)  # type: ignore


class TextDatabase(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.__database = Database()

    def add_documents(self, documents: List[Document]):
        Thread(
            target=_write_docs_to_disk,
            kwargs={"documents": documents},
            daemon=False,
        ).start()

        with self.__database.transaction(raw_connection=True) as cursor:
            self.__database.copy_from(
                cursor,
                "documents",
                columns=DOCUMENT_COLUMNS,
                data=[d.insert_values() for d in documents],
            )
            self.__database.copy_from(
                cursor,
                "text",
                columns=TEXT_COLUMNS,
                data=[d.text.insert_values() for d in documents],
            )
            all_annotations = list(
                a.insert_values()
                for a in itertools.chain(*[doc.text.all_annotations for doc in documents if doc.text is not None])
                if a.type != "token"
            )
            self.__database.copy_from(
                cursor,
                "text_annotations",
                columns=TEXT_ANNOTATION_COLUMNS,
                data=all_annotations,
            )

    @property
    def doc_count(self):
        with self.__database.session() as session:
            return session.query(DocumentsTable).count()

    def random_sentences(self, count: int) -> List[str]:
        with self.__database.session() as session:
            annotations: List[TextAnnotationsTable] = session.query(TextAnnotationsTable) \
                .options(noload("*")) \
                .filter(TextAnnotationsTable.type_ == "sentence" and TextAnnotationsTable.metadata_[
                "is_stopword"] is False).order_by(func.random()).limit(count).all()  # type:ignore

            return [a.text for a in annotations]  # type: ignore

    def get_documents(
        self, offset: int = 0, limit: int = 1000
    ) -> Generator[Document, None, None]:
        with self.__database.connection() as session:
            stmt = db.select(DocumentsTable.id).offset(offset).limit(limit)
            doc_ids = session.execute(stmt).fetchall()
        for record in doc_ids:
            doc_id = record[0]
            json_file = os.path.join(config.DOCUMENTS_DIR, f"{doc_id}.json.gz")
            if os.path.exists(json_file):
                try:
                    with gzip.open(json_file) as fp:
                        yield Document.from_json(json.load(fp))
                except Exception as e:
                    print(e)
                    continue

    def search(self,
               query: str,
               limit: int = 3) -> List[str]:

        query = " OR ".join(query.split())
        sql_query = sql.SQL("""
                            SELECT distinct text, pgroonga_score(tableoid, ctid) as rank
                            FROM text_annotations
                            WHERE type = 'sentence'
                              and text &@~ (%s, ARRAY [1], ARRAY ['scorer_tf_idf($index)'], 'ml_text_search_index')::pgroonga_full_text_search_condition_with_scorers
                            ORDER BY rank desc
                            LIMIT %s
                            """)

        with self.__database.cursor() as cursor:
            cursor.execute(sql_query,
                           (query, limit))
            result = cursor.fetchall()
            return [sentence[0] for sentence in result]

    def sentence_search(self,
                        embedding: NDArray[np.floating], min_similarity: float, limit: int = 3) -> List[str]:
        binarized_embedding = binarize(embedding)
        max_difference = np.shape(embedding)[0] - min_similarity * np.shape(embedding)[0]
        query = sql.SQL("""
                        SELECT distinct text, (embedding <~> %s) as distance
                        FROM text_annotations
                        WHERE type = 'sentence'
                          and (embedding <~> %s) <= %s
                          and (metadata ->> 'is_stopword')::boolean = false
                        ORDER BY distance
                        LIMIT %s
                        """)
        with self.__database.cursor() as cursor:
            cursor.execute(query,
                           (binarized_embedding, binarized_embedding, max_difference, limit))
            result = cursor.fetchall()
            return [sentence[0] for sentence in result]
