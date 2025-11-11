import itertools
import json
import os
from collections.abc import Generator
from threading import Thread
from typing import Iterable

from psycopg import sql

from lang3s import config
from lang3s.db.database import Database
from lang3s.types import Document, Text, TextAnnotation
from lang3s.utils import decorators


def _write_docs_to_disk(documents: Iterable[Document]):
    documents_dir = config.DOCUMENTS_DIR
    os.makedirs(documents_dir, exist_ok=True)

    for doc in documents:
        doc_path = os.path.join(documents_dir, f"{doc.id}.json")
        with open(doc_path, "w") as fp:
            json.dump(doc.to_json(), fp)


@decorators.singleton
class TextDatabase:
    def __init__(self) -> None:
        self.__database = Database()

    def add_documents(self, documents: Iterable[Document]):
        Thread(
            target=_write_docs_to_disk,
            kwargs={"documents": documents},
            daemon=False,
        ).start()

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
                if a.type != "token"
            )
            self.__database.copy_from(
                cursor,
                "text_annotations",
                columns=TextAnnotation.DB_COLUMNS,
                data=all_annotations,
            )

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
                        SELECT docs.id as doc_id
                        FROM documents as docs
                        ORDER BY docs.id
                        OFFSET %s
                        LIMIT %s
                    """
            )

            cursor.execute(
                query,
                (offset, limit),
            )

            for record in cursor:
                doc_id = record["doc_id"]
                json_file = os.path.join(config.DOCUMENTS_DIR, f"{doc_id}.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file) as fp:
                            yield Document.from_json(json.load(fp))
                    except Exception:
                        continue
