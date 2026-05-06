import time
import traceback
from collections import defaultdict
from typing import Dict, Generator, Iterable, List, Optional

import shortuuid
from lang3s_job_service import File
from spacy.tokens import Doc

from lang3s.nlp.core_nlp import (
    CoreLanguageProcessor,
    convert_to_lang3s,
    core_nlp,
)
from lang3s.nlp.heavy_nlp import heavy_nlp
from lang3s.nlp.metadata import Metadata
from lang3s.nlp.shared_types import Document, Text
from lang3s.pipeline.langdetect import detect_language
from lang3s.utils import partition_generator
from lang3s.utils.formatters import format_duration
from lang3s.utils.logger import get_logger

from .doc_builder import document_generator

logger = get_logger("PIPELINE")


def _group_documents_by_language(docs: List[Document]):
    docs_by_language: Dict[str, List[Document]] = defaultdict(list)
    for doc in docs:
        if doc.text:
            if Metadata.LANGUAGE.value not in doc:
                language = detect_language(doc.text.text)
                doc[Metadata.LANGUAGE] = language
            doc.text[Metadata.LANGUAGE] = doc[Metadata.LANGUAGE]
            docs_by_language[doc[Metadata.LANGUAGE.value]].append(doc)
    return docs_by_language


def _process_spacy_docs(documents: list[Doc]) -> list[Document]:
    new_documents = []
    for doc in documents:
        doc_id = shortuuid.uuid()
        text = Text(
            doc_id=doc_id, content=doc.text, metadata={Metadata.LANGUAGE: doc.lang_}
        )
        lang3s_document = Document(
            id=doc_id,
            text=text,
            metadata={Metadata.LANGUAGE: doc.lang_},
            title=doc_id,
        )
        convert_to_lang3s(doc, lang3s_document)
        new_documents.append(lang3s_document)
    return new_documents


class PretokenizedTokenizer:
    def __init__(self, vocab):
        self.vocab = vocab

    def __call__(self, words):
        return Doc(self.vocab, words=words)


def pipeline_from_tokens(
    documents: Iterable[list[str]],
    language: str,
    batch_size: int = 100,
    tasks: Optional[Iterable[str]] = None,
    disable_ner: bool = False,
    log: bool = True,
) -> List[Document]:
    nlp = CoreLanguageProcessor().get_pipeline(language)
    tokenizer = nlp.tokenizer
    nlp.tokenizer = PretokenizedTokenizer(nlp.vocab)

    docs = []
    try:
        for batch in partition_generator(iter(documents), batch_size):
            start_time = time.perf_counter()
            spacy_docs = [Doc(nlp.vocab, words=tokens) for tokens in batch]
            for name, component in nlp.pipeline:
                spacy_docs = [component(spacy_doc) for spacy_doc in spacy_docs]
            lang3s_docs = _process_spacy_docs(spacy_docs)
            if log:
                logger.info(
                    f"Processed {len(batch)} documents for core processing. {format_duration(start_time, time.perf_counter())}"
                )
            _perform_heavy(lang3s_docs, tasks=tasks, log=log, disable_ner=disable_ner)

            docs.extend(lang3s_docs)
    finally:
        nlp.tokenizer = tokenizer

    return docs


def pipeline(
    files: Iterable[File],
    batch_size: int = 100,
    tasks: Optional[Iterable[str]] = None,
    log: bool = True,
    disable_ner: bool = False,
    is_reannotation: bool = False,
) -> Generator[Document, None, None]:
    """
    Processes raw text into annotated documents.
    """
    for batch in partition_generator(document_generator(files), batch_size):
        docs_by_language = _group_documents_by_language(batch)

        start_time = time.perf_counter()
        for language, language_docs in docs_by_language.items():
            core_nlp(language, language_docs)

        if log:
            logger.info(
                f"Processed {len(batch)} documents for core processing. {format_duration(start_time, time.perf_counter())}"
            )

        _perform_heavy(
            batch,
            tasks=tasks,
            log=log,
            disable_ner=disable_ner,
            is_reannotation=is_reannotation,
        )

        for doc in batch:
            yield doc


def _perform_heavy(
    batch: list[Document],
    tasks: Optional[Iterable[str]] = None,
    log: bool = True,
    disable_ner: bool = False,
    is_reannotation: bool = False,
):
    start_time = time.perf_counter()
    for doc in batch:
        try:
            heavy_nlp(
                doc,
                tasks=tasks,
                disable_ner=disable_ner,
                is_reannotation=is_reannotation,
            )
        except Exception as e:
            logger.error(e)
            traceback.print_exc()
    if log:
        logger.info(
            f"Processed {len(batch)} documents for heavy processing. {format_duration(start_time, time.perf_counter())}"
        )
