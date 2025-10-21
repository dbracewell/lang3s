import itertools
import time
from typing import List

from lang3s.core import Document, TextAnnotation
from lang3s.utils import partition

from .tables import Documents, Text, TextAnnotations, database


def __create_annotation(a: TextAnnotation):
    return {
        "doc": a.doc_id,
        "embedding": a.embedding,
        "end": a.end,
        "start": a.start,
        "text": a.text,
        "text_id": a.owner.id,
        "type": a.type,
        "value": a.value,
        "metadata": a.metadata,
    }


def __annotations(doc: Document):
    if doc.text is None:
        return []
    return itertools.chain(
        [__create_annotation(t) for t in doc.text.tokens],
        [__create_annotation(s) for s in doc.text.sentences],
        [__create_annotation(a) for a in doc.text.annotations],
    )


def __insert_docs(docs: List[Document]):
    doc_inserts = [
        {"id": doc.id, "title": doc.title, "metadata": doc.metadata} for doc in docs
    ]
    for batch in partition(doc_inserts, 500):
        Documents.insert_many(batch).execute()


def __insert_text(docs: List[Document]):
    text_inserts = [
        {
            "doc_id": doc.id,
            "id": doc.text.id,
            "text": doc.text.text,
            "embedding": doc.text.embedding,
            "metadata": doc.text.metadata,
        }
        for doc in docs
        if doc.text is not None
    ]
    if len(text_inserts) > 0:
        for batch in partition(text_inserts, 500):
            Text.insert_many(batch).execute()


def __insert_text_annotations(docs: List[Document]):
    annotation_insert = list(
        itertools.chain.from_iterable(list(__annotations(doc)) for doc in docs)
    )
    if len(annotation_insert) > 0:
        for batch in partition(annotation_insert, 500):
            TextAnnotations.insert_many(batch).execute()


@database.atomic()
def add_documents_to_db(docs: List[Document]):
    if len(docs) < 1:
        return
    start = time.perf_counter()
    __insert_docs(docs)
    __insert_text(docs)
    __insert_text_annotations(docs)
    end = time.perf_counter()
    print(f"Database Insert: {end - start:.6f}")
