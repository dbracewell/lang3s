from lang3s_job_service import File

from lang3s.data.parsers.parser import ParseFn
from lang3s.data.parsers.text.html import parse_html
from lang3s.data.parsers.text.markdown import parse_markdown
from lang3s.data.parsers.text.plain_text import parse_plain_text
from lang3s.nlp.shared_types import Document, Text

from .core import (
    build_base_metadata,
    get_or_create_doc_id,
)


def text_to_document(file: File) -> Document:
    parser: ParseFn = parse_plain_text
    if file.mime_type == "text/html":
        parser = parse_html
    elif file.mime_type in ("text/markdown", "text/x-markdown"):
        parser = parse_markdown

    parse = parser(text=file.content, encoding=file.encoding)
    doc_id = get_or_create_doc_id(file)
    base_metadata, title = build_base_metadata(file, doc_id)
    text = Text(
        doc_id=doc_id,
        content=parse.content,
    )
    base_metadata.update(parse.metadata)
    return Document(
        id=doc_id,
        text=text,
        title=parse.metadata.pop("title", title),
        metadata=base_metadata,
    )
