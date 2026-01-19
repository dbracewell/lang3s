from lang3s_job_service import File

from lang3s.data.parsers import Parser
from lang3s.data.parsers.text import HtmlParser, MarkDownParser, PlainTextParser
from lang3s.shared_types import Document, Text

from .core import (
    build_base_metadata,
    get_or_create_doc_id,
)


def text_to_document(file: File) -> Document:
    parser: Parser = PlainTextParser()
    if file.mime_type == "text/html":
        parser = HtmlParser()
    elif file.mime_type in ("text/markdown", "text/x-markdown"):
        parser = MarkDownParser()

    parse = parser.parse(text=file.content, encoding=file.encoding)
    doc_id = get_or_create_doc_id(file)
    base_metadata, title = build_base_metadata(file, doc_id)
    text = Text(
        doc_id=doc_id,
        content=parse.content,
    )
    base_metadata.update(parse.metadata)
    return Document(
        doc_id=doc_id,
        text=text,
        title=parse.metadata.pop("title", title),
        metadata=base_metadata,
    )
