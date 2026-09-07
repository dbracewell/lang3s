from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Iterable, Optional

import numpy as np

from lang3s.core.itertools_extras import filter_none
from lang3s.data.schemas import Document, Metadata
from lang3s.ml.math_extras import normalize
from lang3s.nlp.components.coref import get_in_document_coref_model
from lang3s.nlp.components.embedder import Embedder, EmbeddingResult, embedding_dtype
from lang3s.nlp.components.events import extract_events_for_doc
from lang3s.nlp.components.heavy_tagger import heavy_tagger
from lang3s.nlp.components.ner import get_ner_model

if TYPE_CHECKING:
    from lang3s.data.schemas import Event, TextAnnotation


def heavy_nlp(
    doc: Document,
    tasks: Optional[Iterable[str]] = None,
    is_reannotation: bool = False,
    disable_ner: bool = False,
):
    if doc.text is None:
        return

    embedder = Embedder()
    embedder.model.eval()

    sentences = [[t.content for t in s.tokens] for s in doc.text.sentences]
    result = embedder(
        sentences,
        is_split_into_words=True,
    )

    if not is_reannotation:
        create_core_embeddings(doc, result)
    else:
        sources = ["rb_event_extractor", "ner", "coref"]
        if tasks is not None:
            sources += tasks
        doc.text.remove_annotations(sources)

    if not disable_ner:
        ner = get_ner_model()
        ner.process([doc])

    heavy_tagger.tag(
        doc=doc,
        embeddings=result,
        tasks=tasks,
    )

    embed_all(doc)
    if not disable_ner:
        coref_model = get_in_document_coref_model()
        coref_model.perform_coref(doc)

    extract_events_for_doc(doc)
    embed_all(doc)


def create_core_embeddings(doc: Document, result: EmbeddingResult):
    if not result.sentence_embeddings:
        return
    doc_emb = np.zeros(result.sentence_embeddings[0].shape[-1], dtype=embedding_dtype)

    for sentence, word_embeddings, sentence_embedding in zip(
        doc.text.sentences,
        result.word_embeddings,
        result.sentence_embeddings,
    ):
        sentence.embedding = normalize(sentence_embedding).astype(embedding_dtype)
        weight = sentence[Metadata.WEIGHT.value]
        if weight > 0:
            doc_emb += sentence_embedding * float(weight)

        # Assign the token embeddings
        for token, emb in zip(sentence.tokens, word_embeddings):
            token.embedding = emb.astype(embedding_dtype)

    # Document level embedding is the weighted sum of the
    # sentence embeddings
    doc.text.embedding = normalize(doc_emb).astype(embedding_dtype)


def embed_all(doc):
    for annotation in doc.text.annotations:
        if annotation.embedding.sum() != 0.0:
            continue
        if annotation.is_eventive:
            embed_event_annotation(annotation)
        else:
            embed_annotation(annotation)


def _to_mean_array(
    embeddings: list[list[np.ndarray]],
) -> Optional[np.ndarray]:
    if len(embeddings) == 0:
        return None
    return np.array(list(itertools.chain.from_iterable(embeddings))).mean(axis=0)


def embed_event_annotation(annotation: TextAnnotation):
    event: Event = annotation.frames[0]
    trigger_embedding = np.array([t.embedding for t in annotation.tokens]).mean(axis=0)

    a0_embedding = _to_mean_array([[t.embedding for t in a.tokens] for a in event.a0])
    a1_embedding = _to_mean_array([[t.embedding for t in a.tokens] for a in event.a1])

    e = filter_none([a0_embedding, a1_embedding])
    if len(e) == 1:
        sum_embedding = 0.2 * e[0]
    elif len(e) == 2:
        sum_embedding = 0.2 * e[0] + 0.2 * e[1]
    else:
        raise ValueError("Something went wrong", event)

    sum_embedding += (1.0 - 0.2 * len(e)) * trigger_embedding
    annotation.embedding = sum_embedding.astype(embedding_dtype)


def embed_annotation(annotation: TextAnnotation):
    if np.sum(annotation.embedding) != 0:
        return
    annotation.embedding = (
        np.array([t.embedding for t in annotation.tokens])
        .mean(axis=0)
        .astype(embedding_dtype)
    )
    if np.any(np.isnan(annotation.embedding)):
        annotation.embedding = np.nan_to_num(annotation.embedding).astype(
            embedding_dtype
        )
