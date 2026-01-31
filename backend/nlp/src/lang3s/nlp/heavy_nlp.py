import itertools
import logging
from typing import Iterable, List, Optional

import numpy as np
from numpy.typing import NDArray

from lang3s.models.embedder import Embedder, EmbeddingResult
from lang3s.models.transformer.multi_task_transformer import MultiTaskTransformer
from lang3s.models.transformer.shared_types import TokenLabelResult
from lang3s.nlp.event_extraction import extract_events
from lang3s.nlp.keyword_extraction import extract_keywords
from lang3s.nlp.shared_types import Document, Event, Metadata, TextAnnotation
from lang3s.utils import filter_none
from lang3s.utils.maths import normalize

logger = logging.getLogger(__name__)


embedding_dtype = np.float16


def heavy_nlp(
    doc: Document,
    tasks: Optional[Iterable[str]] = None,
    is_reannotation: bool = False,
    embedder: Optional[Embedder] = None,
    mtask: Optional[MultiTaskTransformer] = None,
):
    embedder = embedder if embedder is not None else Embedder()
    embedder.model.eval()

    if doc.text is None:
        return

    sentences = [[t.text for t in s.tokens] for s in doc.text.sentences]
    result = embedder(
        sentences,
        is_split_into_words=True,
    )

    if not is_reannotation:
        create_core_embeddings(doc, result)
    else:
        sources = ["rb_event_extractor"]
        if tasks is not None:
            sources += tasks
        doc.text.remove_annotations(sources)

    perform_heavy_tagging(doc, sentences, result, tasks, mtask=mtask)
    extract_events_for_doc(doc)

    for annotation in doc.text.annotations:
        embed_annotation(annotation)

    keywords = extract_keywords(doc.text, top_n=10)
    doc.text.keywords = keywords


def _to_mean_array(
    embeddings: List[List[NDArray[np.floating]]],
) -> Optional[NDArray[np.floating]]:
    if len(embeddings) == 0:
        return None
    return np.array(list(itertools.chain.from_iterable(embeddings))).mean(axis=0)


def embed_event_annotation(annotation: TextAnnotation):
    event: Event = annotation.events[0]
    trigger_embedding = np.array([t.embedding for t in annotation.tokens]).mean(axis=0)

    a0_embedding = _to_mean_array([[t.embedding for t in a.tokens] for a in event.A0])
    a1_embedding = _to_mean_array([[t.embedding for t in a.tokens] for a in event.A1])

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

    if annotation.type == "event":
        embed_event_annotation(annotation)
    else:
        annotation.embedding = (
            np.array([t.embedding for t in annotation.tokens])
            .mean(axis=0)
            .astype(embedding_dtype)
        )
    if np.any(np.isnan(annotation.embedding)):
        logger.error(
            f"Error: NaN value in embedding for {annotation.text} {[t.text for t in annotation.tokens]} ",
            exc_info=True,
        )
        annotation.embedding = np.nan_to_num(annotation.embedding).astype(
            embedding_dtype
        )


def create_core_embeddings(doc: Document, result: EmbeddingResult):
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


def _add_token_span(
    start: Optional[int],
    end: int,
    doc: Document,
    sentence: TextAnnotation,
    annotation_type: str,
    source_name: str,
    label: Optional[str],
):
    if start is not None and label is not None:
        doc.text.add_annotation(
            text=" ".join([t.text for t in sentence.tokens[start:end]]),
            start=start + sentence.start,
            end=end + sentence.start,
            sentence_id=sentence.sentence_id,
            type=annotation_type,
            source=source_name,
            value=label,
        )


def perform_heavy_tagging(
    doc: Document,
    sentences: List[List[str]],
    result: EmbeddingResult,
    tasks: Optional[Iterable[str]],
    mtask: Optional[MultiTaskTransformer],
):
    tagger = mtask if mtask is not None else MultiTaskTransformer()
    outputs = tagger.forward(
        result, sentences=sentences, language=doc.language, tasks=tasks
    )

    for source_name, output in outputs.items():
        if output.task_type.is_sentence_level():
            for l, sentence in zip(output.labels, doc.text.sentences):
                label, prob = l  # type: ignore
                if label is not None and len(label) > 0:
                    sentence[output.annotation_type] = {
                        "value": label,
                        "source": source_name,
                        "confidence": prob,
                    }

        else:
            all_labels: TokenLabelResult = output.labels
            for sentence, sentence_labels in zip(doc.text.sentences, all_labels):
                for label, start, end in sentence_labels:
                    _add_token_span(
                        start=start,
                        end=end,
                        sentence=sentence,
                        annotation_type=output.annotation_type,
                        source_name=source_name,
                        label=label,
                        doc=doc,
                    )


def extract_events_for_doc(doc: Document):
    events = extract_events(doc)
    for event in events:
        if len(event.A0) == 0 and len(event.A1) == 0:
            continue
        doc.text.add_annotation(
            text=event.trigger.text,
            start=event.trigger.start,
            end=event.trigger.end,
            sentence_id=event.trigger.sentence_id,
            type=event.trigger.type,
            value=event.trigger.value,
            source="rb_event_extractor",
            metadata={
                Metadata.LEMMA: event.trigger.lemma,
                Metadata.A0: [a0.id for a0 in event.A0],
                Metadata.A0_TEXT: [a0.text for a0 in event.A0],
                Metadata.A1: [a1.id for a1 in event.A1],
                Metadata.A1_TEXT: [a1.text for a1 in event.A1],
                Metadata.TIME: event.TIME.id if event.TIME is not None else None,
                Metadata.LOC: event.LOC.id if event.LOC is not None else None,
                Metadata.TIME_TEXT: event.TIME.text if event.TIME is not None else None,
                Metadata.LOC_TEXT: event.LOC.text if event.LOC is not None else None,
            },
        )
