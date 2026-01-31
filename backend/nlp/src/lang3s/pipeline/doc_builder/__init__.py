from typing import Callable, Dict, Generator, Iterable

from lang3s_job_service import File

from lang3s.nlp.shared_types import Document

from .text import (
    text_to_document,
)

type DocumentCreator = Callable[[File], Document]

__CONVERTERS: Dict[str, DocumentCreator] = {}


def create_document(file: File) -> Document:
    """
    Create a new document from a file.
    """
    if file.mime_type.startswith("text/"):
        return text_to_document(file)
    return __CONVERTERS.get(file.mime_type, text_to_document)(file)


def document_generator(files: Iterable[File]) -> Generator[Document, None, None]:
    """
    Generator that yields new documents from a file.
    """
    for file in files:
        yield create_document(file)
