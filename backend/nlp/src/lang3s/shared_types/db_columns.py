from collections import namedtuple

TEXT_ANNOTATION_COLUMNS = [
    "id",
    "text_id",
    "doc_id",
    "start",
    "end",
    "sentence_id",
    "type",
    "value",
    "source",
    "text",
    "clean_text",
    "mapping",
    "embedding",
    "full_embedding",
    "metadata",
]

TextAnnotationRow = namedtuple("TextAnnotationRow", TEXT_ANNOTATION_COLUMNS)

TEXT_COLUMNS = [
    "id",
    "text",
    "doc_id",
    "embedding",
    "full_embedding",
    "metadata",
]

TextRow = namedtuple("TextRow", TEXT_COLUMNS)

DOCUMENT_COLUMNS = ["id", "title", "metadata"]

DocumentRow = namedtuple("DocumentRow", DOCUMENT_COLUMNS)
