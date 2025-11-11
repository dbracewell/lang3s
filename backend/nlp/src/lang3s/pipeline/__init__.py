import logging
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from lang3s_job_service import File

from lang3s.db.text_database import TextDatabase
from lang3s.nlp.core_nlp import core_nlp
from lang3s.nlp.heavy_nlp import heavy_nlp
from lang3s.pipeline.langdetect import detect_language
from lang3s.types import Document
from lang3s.types.core_types import Text
from lang3s.types.metadata import Metadata
from lang3s.utils import partition_generator

from .doc_builder import create_document

logger = logging.getLogger(__name__)


def _generate_documents(files: Iterable[File]) -> Iterable[Document]:
    for file in files:
        yield create_document(file)


def _group_documents_by_language(docs: List[Document]):
    docs_by_language: Dict[str, List[Text]] = defaultdict(list)
    for doc in docs:
        if doc.text:
            if Metadata.LANGUAGE.value not in doc.metadata:
                language = detect_language(doc.text.text)
                doc.metadata[Metadata.LANGUAGE.value] = language
            docs_by_language[doc.metadata[Metadata.LANGUAGE.value]].append(
                doc.text
            )
    return docs_by_language


def pipeline(
    files: Iterable[File],
    write_to_db: bool = False,
    batch_size: int = 100,
    tasks: Optional[Iterable[str]] = None,
) -> List[Document]:
    text_db = TextDatabase()

    docs = []
    for batch in partition_generator(_generate_documents(files), batch_size):
        docs_by_language = _group_documents_by_language(batch)

        start = time.perf_counter()
        logger.info(
            f"✍️ Starting annotation on {len(batch)} documents in {len(docs_by_language)} language(s)."
        )

        for language, language_docs in docs_by_language.items():
            core_nlp(language, language_docs)

        for doc in batch:
            try:
                heavy_nlp(doc, tasks)
            except Exception as e:
                logger.error("Error Processing Document: ", e)
                import traceback

                traceback.print_exc()

        end = time.perf_counter()

        logger.info(
            f"✍️ Finished annotation of {len(batch)} documents: {(end - start):.2f}s"
        )
        docs.extend(batch)

        if write_to_db:
            start = time.perf_counter()
            logger.info(
                f"💽 Starting writing of {len(batch)} documents to database"
            )
            text_db.add_documents(batch)
            end = time.perf_counter()
            logger.info(
                f"💽 Finished writing {len(batch)} documents to database: {(end - start):.2f}s"
            )

    return docs
