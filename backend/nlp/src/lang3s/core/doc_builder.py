import base64
import os
from typing import Callable, Dict, Optional, cast

import shortuuid

from lang3s.io import File

from .core_types import Document, Metadata, Text


def __normalize(text: str) -> str:
    return " ".join(text.split())


def __decode(content: str, encoding: Optional[str], mime_type: str):
    if encoding is None:
        return content
    decoded = base64.b64decode(content)
    if mime_type.lower().startswith("text"):
        return decoded.decode("utf-8")
    return decoded


def __text_to_document(file: File) -> Document:
    doc_id = shortuuid.uuid()
    text = Text(
        doc_id=doc_id,
        content=__normalize(
            cast(
                str,
                __decode(
                    file.content, encoding=file.encoding, mime_type=file.mime_type
                ),
            )
        ),
    )
    metadata = {
        Metadata.PATH.value: file.path,
        Metadata.MIME_TYPE.value: file.mime_type,
    }
    metadata.update(file.metadata)
    return Document(
        doc_id=doc_id,
        text=text,
        title=(
            file.metadata["title"]
            if "title" in file.metadata
            else os.path.basename(file.path)
        ),
        metadata=metadata,
    )


__CONVERTERS: Dict[str, Callable[[File], Document]] = {
    "text/plain": __text_to_document,
    "text/html": __text_to_document,
}


def create_document(file: File) -> Document:
    return __CONVERTERS.get(file.mime_type, __text_to_document)(file)
