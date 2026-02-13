import time
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from joblib import Parallel, delayed
from lang3s_job_service import File

from lang3s.models import Embedder, MultiTaskTransformer
from lang3s.nlp.core_nlp import core_nlp
from lang3s.nlp.heavy_nlp import heavy_nlp
from lang3s.nlp.shared_types import Document, Metadata
from lang3s.pipeline.langdetect import detect_language
from lang3s.utils import partition_generator
from lang3s.utils.logger import get_logger

from ..utils.formatters import format_duration
from .doc_builder import document_generator

logger = get_logger("PIPELINE")


def _group_documents_by_language(docs: List[Document]):
    docs_by_language: Dict[str, List[Document]] = defaultdict(list)
    for doc in docs:
        if doc.text:
            if Metadata.LANGUAGE.value not in doc:
                language = detect_language(doc.text.text)
                doc[Metadata.LANGUAGE.value] = language
            docs_by_language[doc[Metadata.LANGUAGE.value]].append(doc)
    return docs_by_language


def pipeline(
    files: Iterable[File],
    batch_size: int = 100,
    tasks: Optional[Iterable[str]] = None,
    embedder: Optional[Embedder] = None,
    mtask: Optional[MultiTaskTransformer] = None,
    log: bool = True,
) -> List[Document]:
    """
    Processes raw text into annotated documents.
    """
    docs = []

    for batch in partition_generator(document_generator(files), batch_size):
        docs_by_language = _group_documents_by_language(batch)

        start_time = time.perf_counter()
        for language, language_docs in docs_by_language.items():
            core_nlp(language, language_docs)

        if log:
            logger.info(
                f"Processed {len(batch)} documents for core processing. {format_duration(start_time, time.perf_counter())}"
            )

        start_time = time.perf_counter()
        Parallel(n_jobs=-1)(
            delayed(heavy_nlp)(doc, tasks, embedder, mtask) for doc in batch
        )

        # worker_func = partial(heavy_nlp, tasks=tasks, embedder=embedder, mtask=mtask)
        # with multiprocessing.Pool(processes=2) as pool:
        #     pool.map(worker_func, batch)
        # for doc in batch:
        #     try:
        #         heavy_nlp(
        #             doc,
        #             tasks,
        #             embedder=embedder,
        #             mtask=mtask,
        #         )
        #     except Exception:
        #         logger.error("Error Processing Document: ", exc_info=True)

        if log:
            logger.info(
                f"Processed {len(batch)} documents for heavy processing. {format_duration(start_time, time.perf_counter())}"
            )

        docs.extend(batch)

    return docs
