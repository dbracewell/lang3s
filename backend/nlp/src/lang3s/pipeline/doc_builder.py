import base64
import html
import os
from typing import Callable, Dict, Optional

import shortuuid
from lang3s_job_service import File

from lang3s.shared_types import Document, Metadata, Text


def __normalize(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\u200b", "")
    return " ".join(text.split())


def __decode(content: str, encoding: Optional[str], mime_type: str):
    if encoding is None:
        return content
    decoded = base64.b64decode(content)
    if mime_type.lower().startswith("text"):
        return decoded.decode("utf-8")
    return decoded


def __build_metadata(file: File, doc_id: str):
    metadata = {
        Metadata.MIME_TYPE.value: file.mime_type,
    }
    if file.path is not None:
        metadata["path"] = file.path

    metadata.update(file.metadata)

    title = file.metadata.get("title", None)
    if title is None and file.path is not None:
        title = os.path.basename(file.path)
    elif title is None:
        title = doc_id

    if "title" in metadata:
        del metadata["title"]

    return metadata, title


def __html_to_document(file: File) -> Document:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        __decode(
            file.content,
            encoding=file.encoding,
            mime_type=file.mime_type,
        ),
        "html.parser",
    )
    doc_id = shortuuid.uuid()
    text = Text(
        doc_id=doc_id,
        content=__normalize(soup.get_text()),
    )
    metadata, title = __build_metadata(file, doc_id)
    return Document(
        doc_id=doc_id,
        text=text,
        title=title,
        metadata=metadata,
    )


def __text_to_document(file: File) -> Document:
    doc_id = shortuuid.uuid()
    text = Text(
        doc_id=doc_id,
        content=__normalize(
            __decode(
                file.content,
                encoding=file.encoding,
                mime_type=file.mime_type,
            ),
        ),
    )
    metadata, title = __build_metadata(file, doc_id)
    return Document(
        doc_id=doc_id,
        text=text,
        title=title,
        metadata=metadata,
    )


__CONVERTERS: Dict[str, Callable[[File], Document]] = {
    "text/plain": __text_to_document,
    "text/html": __html_to_document,
}


def create_document(file: File) -> Document:
    return __CONVERTERS.get(file.mime_type, __text_to_document)(file)
