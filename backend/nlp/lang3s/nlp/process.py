import multiprocessing
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Dict, List, Optional, Set

from lang3s.core import Document, Metadata, Text
from lang3s.nlp.AdapterModelTagger import AdapterModelTagger
from lang3s.nlp.embedding import Embedder

from .core_nlp import core_nlp
from .langdetect import detect_language

tagger = AdapterModelTagger()
embedder = Embedder()


def tag_batch(doc: Document, tasks: Optional[Set[str]]):
    tagger.tag(doc, tasks=tasks)
    embedder.embed_doc(doc)


def nlp(docs: List[Document], tasks: Optional[Set[str]] = None):
    docs_by_language: Dict[str, List[Text]] = defaultdict(list)
    for doc in docs:
        if doc.text:
            if Metadata.LANGUAGE.value not in doc.metadata:
                language = detect_language(doc.text.text)
                doc.metadata[Metadata.LANGUAGE.value] = language
            docs_by_language[doc.metadata[Metadata.LANGUAGE.value]].append(doc.text)

    start = time.perf_counter()
    for language, language_docs in docs_by_language.items():
        core_nlp(language, language_docs)
    with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() - 1) as ex:
        list(ex.map(partial(tag_batch, tasks=tasks), docs))
    end = time.perf_counter()
    print(f"NLP Processing: {(end - start):.6f}")
