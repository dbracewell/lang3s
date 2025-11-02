import itertools
import time
from collections.abc import Generator
from typing import Iterable

from psycopg import sql

from lang3s.db.database import Database, alias_identifier
from lang3s.types import Document, Text, TextAnnotation


class TextDatabase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.__database = Database()

    def add_documents(self, documents: Iterable[Document]):
        start = time.perf_counter()
        with self.__database.transaction() as cursor:
            self.__database.copy_from(
                cursor,
                "documents",
                columns=Document.DB_COLUMNS,
                data=[d.insert_values() for d in documents],
            )
            self.__database.copy_from(
                cursor,
                "text",
                columns=Text.DB_COLUMNS,
                data=[d.text.insert_values() for d in documents],
            )
            all_annotations = list(
                a.insert_values()
                for a in itertools.chain(
                    *[
                        doc.text.all_annotations
                        for doc in documents
                        if doc.text is not None
                    ]
                )
            )
            self.__database.copy_from(
                cursor,
                "text_annotations",
                columns=TextAnnotation.DB_COLUMNS,
                data=all_annotations,
            )
        end = time.perf_counter()
        print(f"Inserting Documents: {(end - start):.6f}")

    @property
    def doc_count(self):
        with self.__database.cursor() as cursor:
            cursor.execute("SELECT count(0) as count FROM documents")
            r = cursor.fetchone()
            if r is None:
                return 0
            return r["count"]

    def get_documents(
        self, offset: int = 0, limit: int = 1000
    ) -> Generator[Document, None, None]:
        with self.__database.cursor() as cursor:
            query = sql.SQL(
                """
                        SELECT {}, annotations.a as annotations 
                        FROM  (
                            SELECT *
                            FROM documents
                            ORDER BY id
                            OFFSET %s
                            LIMIT %s
                        ) as docs
                        INNER JOIN text as texts on texts.doc_id = docs.id
                        INNER JOIN (
                            SELECT text_id, json_arrayagg(json_build_object({}) order by start ASC, "end" ASC) as a
                            FROM text_annotations
                            group by text_id
                        ) as annotations on  annotations.text_id = texts.id
                    """
            ).format(
                sql.SQL(", ").join(
                    itertools.chain(
                        [
                            alias_identifier(["docs", c], f"doc_{c}")
                            for c in Document.DB_COLUMNS
                        ],
                        [
                            alias_identifier(["texts", c], f"text_{c}")
                            for c in Text.DB_COLUMNS
                        ],
                    )
                ),
                sql.SQL(", ").join(
                    [
                        sql.SQL(", ").join([sql.Literal(c), sql.Identifier(c)])
                        for c in TextAnnotation.DB_COLUMNS
                    ]
                ),
            )

            cursor.execute(
                query,
                (offset, limit),
            )

            for record in cursor:
                doc = {
                    "id": record["doc_id"],
                    "title": record["doc_title"],
                    "metadata": record["doc_metadata"],
                    "text": {
                        "id": record["text_id"],
                        "doc_id": record["text_doc_id"],
                        "text": record["text_text"],
                        "metadata": record["text_metadata"],
                        "embedding": record["text_embedding"],
                        "annotations": record["annotations"],
                    },
                }
                yield Document.from_json(doc)


# def get_documents_from_db():
#     db = Database()
#     with db.cursor() as cursor:
#         cursor.execute(
#             sql.SQL(
#                 """
#                     SELECT {}, annotations.a as annotations
#                     FROM documents as docs
#                     INNER JOIN text as texts on texts.doc_id = docs.id
#                     INNER JOIN (
#                         SELECT text_id, json_arrayagg(json_build_object({}) order by start ASC, "end" ASC) as a
#                         FROM text_annotations
#                         group by text_id
#                     ) as annotations on  annotations.text_id = texts.id
#                 """
#             ).format(
#                 sql.SQL(", ").join(
#                     itertools.chain(
#                         [
#                             alias_identifier(["docs", c], f"doc_{c}")
#                             for c in Document.DB_COLUMNS
#                         ],
#                         [
#                             alias_identifier(["texts", c], f"text_{c}")
#                             for c in Text.DB_COLUMNS
#                         ],
#                     )
#                 ),
#                 sql.SQL(", ").join(
#                     [
#                         sql.SQL(", ").join([sql.Literal(c), sql.Identifier(c)])
#                         for c in TextAnnotation.DB_COLUMNS
#                     ]
#                 ),
#             )
#         )
#         for record in cursor:
#             doc = {
#                 "id": record["doc_id"],
#                 "title": record["doc_title"],
#                 "metadata": record["doc_metadata"],
#                 "text": {
#                     "id": record["text_id"],
#                     "doc_id": record["text_doc_id"],
#                     "text": record["text_text"],
#                     "metadata": record["text_metadata"],
#                     "embedding": record["text_embedding"],
#                     "annotations": record["annotations"],
#                 },
#             }
#             yield Document.from_json(doc)


# def add_documents_to_db(docs: List[Document]):
#     db = Database()
#     start = time.perf_counter()
#     with db.transaction() as cursor:
#         db.copy_from(
#             cursor,
#             "documents",
#             columns=Document.DB_COLUMNS,
#             data=[d.insert_values() for d in docs],
#         )
#         db.copy_from(
#             cursor,
#             "text",
#             columns=Text.DB_COLUMNS,
#             data=[d.text.insert_values() for d in docs],
#         )
#         all_annotations = list(
#             a.insert_values()
#             for a in itertools.chain(
#                 *[
#                     doc.text.all_annotations
#                     for doc in docs
#                     if doc.text is not None
#                 ]
#             )
#         )
#         db.copy_from(
#             cursor,
#             "text_annotations",
#             columns=TextAnnotation.DB_COLUMNS,
#             data=all_annotations,
#         )
#     end = time.perf_counter()
#     print(f"Inserting Documents: {(end - start):.6f}")
