from typing import Iterable, List, Optional, Set

from lang3s_job_service import File

from lang3s.db.text_database import TextDatabase
from lang3s.types import Document
from lang3s.utils import partition

from .doc_builder import create_document
from .process import nlp


def generate_documents(files: Iterable[File]) -> Iterable[Document]:
    for file in files:
        yield create_document(file)


def pipeline(
    files: Iterable[File],
    write_to_db: bool = False,
    batch_size: int = 500,
    tasks: Optional[Set[str]] = None,
) -> List[Document]:
    text_db = TextDatabase()
    docs = list(generate_documents(files))
    for batch in partition(docs, batch_size):
        nlp(batch, tasks=tasks)
        if write_to_db:
            text_db.add_documents(batch)
    return docs
