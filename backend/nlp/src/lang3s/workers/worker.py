import csv
from typing import List, Set

from lang3s.core import Document
from lang3s.core.doc_builder import create_document
from lang3s.db.helpers import add_documents_to_db
from lang3s.io import File
from lang3s.nlp import nlp


def process_file(files: List[File], tasks: Set[str] | None = None) -> List[Document]:
    docs = [create_document(file) for file in files]
    nlp(docs, tasks=tasks)
    return docs


reader = csv.DictReader(open("/Users/ik/Downloads/archive/data.csv"), dialect="excel")
files: List[File] = []
try:
    for row in reader:
        if row["full_content"].strip() == "":
            continue
        file = File(
            path=row["url"],
            content=row["full_content"],
            mime_type="text/plain",
            metadata={
                "title": row["title"],
                "source": row["source_name"],
                "author": row["author"],
                "published_date": row["published_at"],
            },
        )
        files.append(file)
except Exception:
    pass

docs = process_file(files, tasks=set())
add_documents_to_db(docs)
