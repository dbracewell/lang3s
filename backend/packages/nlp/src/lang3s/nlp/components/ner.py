import threading
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from gliner import GLiNER

from lang3s.core import config
from lang3s.core.logger import get_logger
from lang3s.core.typing_extras import SingletonMeta
from lang3s.data.db import get_ontology
from lang3s.data.schemas import Document, OntologyEntry, TextAnnotation
from lang3s.nlp.language import get_common_person_titles

logger = get_logger("NER")


def _is_valid_label(entry: OntologyEntry) -> bool:
    if not entry.is_leaf:
        return False
    ml_tagged = entry.properties.get("ml_tagged", None)
    if ml_tagged:
        return bool(ml_tagged.value)
    else:
        return True


class NamedEntityRecognition(metaclass=SingletonMeta):
    def __init__(self):
        self._ner_model = GLiNER.from_pretrained(
            "knowledgator/gliner-bi-base-v2.0",
            map_location=config.NER_INFERENCE_DEVICE,
        )
        self._labels = []
        self._label_embeddings = []
        self._prepare_labels()
        self._person_titles = get_common_person_titles("en")

    def _prepare_labels(self):
        ontology = get_ontology()
        self._labels = [
            f"{o.name}: {o.description}"
            for o in ontology["ALL.Entity"].ancestors
            if _is_valid_label(o)
        ]
        self._label_embeddings = self._ner_model.encode_labels(  # type: ignore
            self._labels,
            batch_size=len(self._labels),
        )

    def refresh(self):
        self._prepare_labels()

    def _chunk_documents(
        self, docs: list[str], chunk_size=1000, overlap=200
    ) -> tuple[list[str], list[tuple[int, int]]]:
        """
        Splits a batch of documents into a flat list of chunks.
        Returns:
            - all_chunks: List of text chunks
            - chunk_map: List of (doc_index, start_offset) for each chunk
        """
        all_chunks = []
        chunk_map = []  # Stores (original_doc_index, character_offset)

        for doc_idx, text in enumerate(docs):
            text_len = len(text)
            start = 0

            # Handle empty docs
            if text_len == 0:
                continue

            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunk_text = text[start:end]

                all_chunks.append(chunk_text)
                chunk_map.append((doc_idx, start))

                if end == text_len:
                    break

                start += chunk_size - overlap

        return all_chunks, chunk_map

    def _process_batch(self, docs: list[str]) -> list[list[dict[str, Any]]]:
        if not docs or self._label_embeddings is None:
            return []

        chunks, chunk_map = self._chunk_documents(docs)

        raw_ner_results = []
        if chunks:
            CHUNK_BATCH_SIZE = 32

            for i in range(0, len(chunks), CHUNK_BATCH_SIZE):
                sub_chunks = chunks[i : i + CHUNK_BATCH_SIZE]
                try:
                    batch_res = self._ner_model.batch_predict_with_embeds(  # type: ignore
                        sub_chunks,
                        self._label_embeddings,
                        self._labels,
                        threshold=config.NER_CONFIDENCE_THRESHOLD,
                    )
                    raw_ner_results.extend(batch_res)
                except IndexError:
                    # Handle empty label crash if it occurs
                    raw_ner_results.extend([[] for _ in sub_chunks])
                except Exception as e:
                    print(f"GLiNER Batch Error: {e}")
                    raw_ner_results.extend([[] for _ in sub_chunks])

        doc_entities = defaultdict(list)
        seen_spans = defaultdict(set)  # (doc_idx) -> set of (start, end, label)

        next_entity_id = defaultdict(int)
        for chunk_idx, entities in enumerate(raw_ner_results):
            doc_idx, offset = chunk_map[chunk_idx]
            for ent in entities:
                start = ent["start"]
                end = ent["end"]
                g_start = start + offset
                g_end = end + offset
                label = ent["label"]

                span_sig = (g_start, g_end, label)
                if span_sig not in seen_spans[doc_idx]:
                    seen_spans[doc_idx].add(span_sig)
                    doc_entities[doc_idx].append(
                        {
                            "id": next_entity_id[doc_idx],
                            "text": ent["text"],
                            "label": label,
                            "start": g_start,
                            "end": g_end,
                            "score": ent.get("score", 0.0),
                        }
                    )
                    next_entity_id[doc_idx] += 1

        final_ner_results = []
        for doc_idx in range(len(docs)):
            sorted_entities = sorted(
                doc_entities[doc_idx], key=lambda x: (x["start"], -x["end"])
            )

            deduplicated_entities = []
            for ent in sorted_entities:
                if not deduplicated_entities:
                    deduplicated_entities.append(ent)
                else:
                    last_ent = deduplicated_entities[-1]
                    if ent["start"] >= last_ent["end"]:
                        deduplicated_entities.append(ent)
            final_ner_results.append(deduplicated_entities)

        return final_ner_results

    def _align_clusters(self, span_clusters, text_clusters, ner_entities):
        enriched = []

        for cluster_idx, (spans, texts) in enumerate(zip(span_clusters, text_clusters)):
            cluster_types = []
            linked = []
            new_entity_spans = []

            for span, text in zip(spans, texts):
                c_start, c_end = span
                c_len = c_end - c_start

                found = False
                for ent in ner_entities:
                    e_start, e_end = ent["start"], ent["end"]
                    if ent["label"] in (
                        "Date",
                        "Time",
                        "Cardinal",
                        "Money",
                        "Ordinal",
                        "Quantity",
                        "Percent",
                    ):
                        continue

                    # Intersection
                    i_start = max(c_start, e_start)
                    i_end = min(c_end, e_end)

                    if i_start < i_end:
                        overlap = i_end - i_start
                        coverage = overlap / c_len
                        head_match = (e_start >= c_start) and (e_start <= c_start + 2)

                        if coverage > 0.6 or (head_match and coverage > 0.1):
                            cluster_types.append(ent["label"])
                            linked.append(ent["id"])
                            found = True

                if not found and len(text.split()) < 10:
                    new_entity_spans.append((c_start, c_end, text))

            dominant = (
                Counter(cluster_types).most_common(1)[0][0]
                if cluster_types
                else "Unknown"
            )

            enriched.append(
                {
                    "id": cluster_idx,
                    "dominant_type": dominant,
                    "mentions": new_entity_spans,
                    "linked_ner_entities": list(set(linked)),
                }
            )
        return enriched

    def process(self, documents: list[Document]) -> None:
        for i in range(0, len(documents), 2):
            batch = [d for d in documents[i : i + 2] if d.text is not None]
            results = self._process_batch([d.text.content for d in batch])
            entity_id_annotation_map: dict[int, TextAnnotation] = {}

            for entities, document in zip(results, batch):
                for entity in entities:
                    start_token = document.text.get_token_for_char_offset(
                        entity["start"],
                    )
                    end_token = document.text.get_token_for_char_offset(
                        entity["end"] - 1,
                    )
                    previous_token = start_token.previous_token()
                    if (
                        previous_token
                        and previous_token.content.lower() in self._person_titles
                    ):
                        entity["label"] = "Person"

                    annotation = document.text.add_annotation(
                        content=document.text.content[
                            start_token["start_char"] : end_token["end_char"]
                        ],
                        type_="entity",
                        value=entity["label"],
                        start=start_token.start,
                        end=end_token.end,
                        source="ner",
                        metadata_json={"confidence": entity["score"]},
                        sentence_index=start_token.sentence_index,
                    )
                    annotation.embedding = (
                        np.array([t.embedding for t in annotation.tokens])
                        .mean(axis=0)
                        .astype(np.float16)
                    )

                    entity_id_annotation_map[entity["id"]] = annotation

                document.text.clear_cache()


_ner: NamedEntityRecognition | None = None
_lock = threading.Lock()


def get_ner_model() -> NamedEntityRecognition:
    global _ner
    global _lock
    _lock.acquire()
    try:
        if _ner is None:
            _ner = NamedEntityRecognition()
        return _ner  # type: ignore
    finally:
        _lock.release()
