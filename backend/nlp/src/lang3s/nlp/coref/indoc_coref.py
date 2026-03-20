import threading
from collections import Counter, defaultdict

import torch

from lang3s.data.filestore import FILE_STORE
from lang3s.models.coref_ranker import (
    REVERSE_POS_MAP,
    FastCorefRanker,
    create_coref_mention,
)
from lang3s.nlp.coref.helper import should_perform_coref
from lang3s.nlp.language import is_person_pronoun
from lang3s.nlp.language.en import ACRONYM_EXPANSIONS
from lang3s.nlp.metadata import Metadata
from lang3s.nlp.shared_types import AnnotationTypes, Document, TextAnnotation


def _apply_nominal_sieve(mention, candidates, all_scores, threshold=-1.5):
    """
    Intercepts the neural network's scores. If the network chooses to leave
    the mention unlinked, the sieve applies deterministic rules to catch nominals.
    """
    # 1. Get the neural network's top choice
    predicted_idx: int = torch.argmax(all_scores).item()

    # Don't allow it to be corefed to Person
    is_it_person = (
        mention.get("cleaned") == "it"
        and predicted_idx > 0
        and candidates[predicted_idx].get("ner_idx") == 1
    )

    if predicted_idx != 0 and not is_it_person:
        return predicted_idx

    m_pos = REVERSE_POS_MAP.get(mention.get("pos_idx"), "DEFAULT")
    m_gen = mention.get("gender_idx")
    m_ner = mention.get("ner_idx")
    m_text_raw = mention.get("text")
    m_text_clean: str = mention.get("cleaned")
    m_text_lower = m_text_raw.lower()

    # 3. Scan candidates backwards (closest mentions first)
    # all_scores is [dummy_score, cand_1_score, cand_2_score, ...]
    for i in range(len(candidates) - 1, -1, -1):
        c = candidates[i]
        score = all_scores[i + 1].item()

        c_pos = REVERSE_POS_MAP.get(c.get("pos_idx"), "DEFAULT")
        c_gen = c.get("gender_idx")
        c_ner = c.get("ner_idx")
        c_text_raw = c.get("text")
        c_text_clean: str = c.get("cleaned")
        c_text_lower = c_text_raw.lower()

        if m_text_clean == "it" and c_ner == 1:  # No it => Person
            continue

        if m_text_lower == c_text_lower and len(m_text_lower) > 1:
            if m_text_lower in ["us", "it", "who", "may", "am", "pm"]:
                # STRICT mode: They must match casing exactly (e.g., "US" == "US")
                if m_text_raw == c_text_raw:
                    return i + 1
            else:
                # SAFE mode: Case-insensitive is fine, BUT we mathematically block
                # a Pronoun (11) from matching a Non-Pronoun.
                # (Either both are 11, or neither are 11).
                if (m_pos == "PRON") == (c_pos == "PRON"):
                    return i + 1

        # ---------------------------------------------------------
        # PASS 1.5: Sub-String and Acronym Matching
        # ---------------------------------------------------------
        # Rule A: Sub-string overlap for Proper Nouns (e.g., "Eliot Spitzer" -> "Mr Spitzer")
        # If one string is entirely contained within the other, and both are PROPN/Persons.
        if m_pos == "PROPN" and c_pos == "PROPN":
            # Strip titles for cleaner matching
            clean_m = m_text_lower.replace("mr ", "").replace("mrs ", "")
            clean_c = c_text_lower.replace("mr ", "").replace("mrs ", "")

            if clean_m in clean_c or clean_c in clean_m:
                if (
                    len(clean_m) > 3 and len(clean_c) > 3
                ):  # Prevent 'US' from matching 'Just'
                    return i + 1

            # Acronyms like BBB => Better Business Bureau
            if all(c.isupper() for c in m_text_clean):
                clean_m = m_text_clean
            else:
                clean_m = "".join(
                    [c[0] for c in m_text_clean.split() if c[0].isupper()]
                )
            if all(c.isupper() for c in c_text_clean):
                clean_c = c_text_clean
            else:
                clean_c = "".join(
                    [c[0] for c in c_text_clean.split() if c[0].isupper()]
                )

            if clean_c == clean_m and len(clean_m) > 0:
                return i + 1

        # Rule B: Known Hardcoded Acronyms (The "US" exception)
        # For a production pipeline, a tiny hardcoded dictionary saves massive compute.
        if (
            m_text_lower in ACRONYM_EXPANSIONS
            and ACRONYM_EXPANSIONS[m_text_lower] == c_text_lower
        ):
            return i + 1
        if (
            c_text_lower in ACRONYM_EXPANSIONS
            and ACRONYM_EXPANSIONS[c_text_lower] == m_text_lower
        ):
            return i + 1

        if m_pos == "PROPN" and c_pos == "PROPN":
            if m_ner == c_ner and m_ner != 0 and score > threshold:
                return i + 1

        if m_pos == "NOUN" and c_pos == "PROPN":
            if m_gen == c_gen and m_gen != 0 and score > threshold:
                return i + 1

    # If no candidates pass the sieve, accept the network's decision to leave it unlinked
    return predicted_idx


def _extract_entity_clusters(resolved_mentions):
    """
    Uses Union-Find to group pairwise coreference links into global entity clusters.
    """
    # 1. Initialize every mention as its own cluster parent
    parent = {m["id"]: m["id"] for m in resolved_mentions}

    # Path compression: Flattens the tree so future lookups are O(1)
    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    # Union: Merges two clusters together
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # 2. Apply the coreference links we found via PyTorch + Sieve
    for m in resolved_mentions:
        predicted_antecedent_id = m.get("coref_id")
        if predicted_antecedent_id is not None and predicted_antecedent_id != m["id"]:
            union(m["id"], predicted_antecedent_id)

    # 3. Group mentions by their ultimate root parent
    clusters = defaultdict(list)
    for m in resolved_mentions:
        root = find(m["id"])
        clusters[root].append(m)

    # 4. Format for your database (Identify the "Canonical Name" for the cluster)
    db_ready_entities = []

    for root_id, cluster_mentions in clusters.items():
        # The canonical name is usually the first Proper Noun in the cluster
        # Fallback to the longest string if no Proper Noun exists
        proper_nouns = [m for m in cluster_mentions if m.get("pos_idx") == 12]
        entities = [m for m in cluster_mentions if m.get("ner_idx") != 0]
        if proper_nouns:
            canonical_id = max(proper_nouns, key=lambda m: len(m.get("text")))["id"]
        elif entities:
            canonical_id = max(entities, key=lambda m: len(m.get("text")))["id"]
        else:
            canonical_id = max(
                [m for m in cluster_mentions], key=lambda m: len(m.get("text"))
            )["id"]

        types = [m["value"] for m in cluster_mentions if m["value"]]
        best_type = "Person"
        if types:
            best_type = Counter(types).most_common()[0][0]

        db_ready_entities.append(
            {
                "canonical_id": canonical_id,
                "canonical_type": best_type,
                "mentions": cluster_mentions,
            }
        )

    return db_ready_entities


class InDocumentCoref:
    def __init__(self, device: str = "cpu", max_antecedents=50):
        self._model = FastCorefRanker()
        self._model.eval()
        self._device = device
        self._model.to(device)
        self._max_antecedents = max_antecedents

    @classmethod
    def load_coref_model(cls, device="cpu"):
        """
        Loads the model from a saved checkpoint and prepares it for inference.
        """
        filepath = FILE_STORE.get_file_path("models/coref.pt")
        checkpoint = torch.load(filepath, map_location=device, weights_only=True)
        coref_ranker = cls(device=device)
        coref_ranker._model = FastCorefRanker(
            embedding_dim=checkpoint["embedding_dim"],
            hidden_dim=checkpoint["hidden_dim"],
            max_distance_bins=checkpoint["max_distance_bins"],
        )
        coref_ranker._model.load_state_dict(checkpoint["model_state_dict"])
        coref_ranker._model.to(device)
        coref_ranker._model.eval()
        return coref_ranker

    def process_document_batched(self, mentions, features):
        # 1. Flattening arrays
        m_embs, m_pos, m_ner, m_gen = [], [], [], []
        c_embs, c_pos, c_ner, c_gen = [], [], [], []
        dists = []

        # Keeps track of which pair indices belong to which mention
        pair_routing = defaultdict(list)

        # --- PHASE 1: Build the Flattened Batch ---
        for i in range(1, len(mentions)):
            current_mention = mentions[i]
            m_feat = features[i]

            start_idx = max(0, i - self._max_antecedents)
            if current_mention.type == AnnotationTypes.TOKEN:  # Pronoun logic
                start_idx = max(0, i - (self._max_antecedents // 2))

            for j in range(start_idx, i):
                c_feat = features[j]

                m_embs.append(m_feat["emb"])
                m_pos.append(m_feat["pos_idx"])
                m_ner.append(m_feat["ner_idx"])
                m_gen.append(m_feat["gender_idx"])

                c_embs.append(c_feat["emb"])
                c_pos.append(c_feat["pos_idx"])
                c_ner.append(c_feat["ner_idx"])
                c_gen.append(c_feat["gender_idx"])

                dists.append(min(i - j, 9))

                # Map this global pair index back to mention 'i'
                pair_routing[i].append(len(dists) - 1)

        if not dists:
            return  # No valid pairs in this document

        device = self._device

        # --- PHASE 2: The Single GPU Pass ---
        # Convert lists to tensors and move to MPS/GPU
        batched_m = {
            "emb": torch.stack(m_embs),
            "pos_idx": torch.tensor(m_pos, device=device),
            "ner_idx": torch.tensor(m_ner, device=device),
            "gender_idx": torch.tensor(m_gen, device=device),
        }

        batched_c = {
            "emb": torch.stack(c_embs),
            "pos_idx": torch.tensor(c_pos, device=device),
            "ner_idx": torch.tensor(c_ner, device=device),
            "gender_idx": torch.tensor(c_gen, device=device),
        }

        batched_dists = torch.tensor(dists, device=device)

        with torch.inference_mode():
            # This single line replaces your entire previous PyTorch for-loop!
            global_scores = self._model.batch_predict(
                batched_m, batched_c, batched_dists
            )

            # Get the dummy score tensor once
            dummy = self._model.dummy_score.view(1)

        # --- PHASE 3: Reconstruct and Sieve ---
        for i in range(1, len(mentions)):
            indices = pair_routing.get(i)
            if not indices:
                continue

            current_feature = features[i]
            start_idx = max(0, i - self._max_antecedents)
            if mentions[i].type == AnnotationTypes.TOKEN:
                start_idx = max(0, i - (self._max_antecedents // 2))

            candidates = mentions[start_idx:i]
            candidate_features = features[start_idx:i]

            # Extract the specific scores for this mention and prepend the dummy score
            mention_specific_scores = global_scores[indices]
            all_scores = torch.cat([dummy, mention_specific_scores])

            # Run your deterministic logic
            best_idx = _apply_nominal_sieve(
                current_feature, candidate_features, all_scores, threshold=-1.5
            )

            if best_idx > 0:
                best_antecedent = candidates[best_idx - 1]
                current_feature["coref_id"] = best_antecedent.id

    def perform_coref(self, document: Document):
        if not document.text:
            return

        # ---------------------------------------------------------
        # MENTION EXTRACTION
        # ---------------------------------------------------------
        mentions = [
            entity for entity in document.text.entities if should_perform_coref(entity)
        ]
        for token in document.text.tokens:
            if (
                token.value == "PRON"
                and (
                    is_person_pronoun(token.text, "en")
                    or token.text.lower() in ("it", "its")
                )
                and not token.entities
            ):
                mentions.append(token)

        mentions.sort(key=lambda x: (x.start, -x.end))
        mention_id_map: dict[str, TextAnnotation] = {
            entity.id: entity for entity in mentions
        }
        features = [create_coref_mention(mention) for mention in mentions]

        # ---------------------------------------------------------
        # BATCH PROCESSING
        # ---------------------------------------------------------
        self.process_document_batched(mentions, features)

        # ---------------------------------------------------------
        # CLUSTERING & DOCUMENT UPDATE
        # ---------------------------------------------------------
        resolved_mentions = _extract_entity_clusters(features)
        for cluster in resolved_mentions:
            canonical_id = cluster["canonical_id"]
            canonical_type = cluster["canonical_type"]
            canonical_mention = mention_id_map[canonical_id]
            if canonical_mention.type == AnnotationTypes.TOKEN:
                continue

            canonical_mention.value = canonical_type

            for mention in cluster["mentions"]:
                m_id = mention["id"]
                if canonical_id == m_id:
                    continue

                mention = mention_id_map[m_id]
                if mention.type == AnnotationTypes.TOKEN:
                    document.text.add_annotation(
                        text=mention.text,
                        start=mention.start,
                        end=mention.end,
                        sentence_id=mention.sentence_id,
                        type="entity",
                        value=canonical_type,
                        source="coref",
                        embedding=mention.embedding,
                        metadata={
                            Metadata.COREF: canonical_mention.id,
                            Metadata.COREF_TEXT: canonical_mention.normalized_text,
                        },
                    )
                else:
                    mention.value = canonical_type
                    mention[Metadata.COREF] = canonical_mention.id
                    mention[Metadata.COREF_TEXT] = canonical_mention.normalized_text

        document.text.clear_cache()

    # def perform_coref(self, document: Document):
    #     if not document.text:
    #         return
    #
    #     mentions = [
    #         entity for entity in document.text.entities if should_perform_coref(entity)
    #     ]
    #     for token in document.text.tokens:
    #         if (
    #             token.value == "PRON"
    #             and (
    #                 is_person_pronoun(token.text) or token.text.lower() in ("it", "its")
    #             )
    #             and not token.entities
    #         ):
    #             mentions.append(token)
    #     mentions.sort(key=lambda x: (x.start, -x.end))
    #     mention_id_map: dict[str, TextAnnotation] = {
    #         entity.id: entity for entity in mentions
    #     }
    #     features = [create_coref_mention(mention) for mention in mentions]
    #
    #     with torch.inference_mode():
    #         for i, current_mention in enumerate(mentions):
    #             if i == 0:
    #                 continue
    #
    #             current_feature = features[i]
    #             start_idx = max(0, i - self._max_antecedents)
    #
    #             if current_mention.type == AnnotationTypes.TOKEN:
    #                 # smaller context for pronouns
    #                 start_idx = max(0, i - (self._max_antecedents // 2))
    #
    #             candidates = mentions[start_idx:i]
    #             candidate_features = features[start_idx:i]
    #             distances = torch.tensor(
    #                 [min(i - (start_idx + j), 9) for j in range(len(candidates))]
    #             )
    #             scores = self._model(
    #                 current_feature,
    #                 candidate_features,
    #                 distances,
    #             )
    #             best_idx: int = _apply_nominal_sieve(
    #                 current_feature, candidate_features, scores, threshold=-1.5
    #             )
    #             if best_idx > 0:
    #                 best_antecedent = candidates[best_idx - 1]
    #                 current_feature["coref_id"] = best_antecedent.id
    #
    #     resolved_mentions = _extract_entity_clusters(features)
    #     for cluster in resolved_mentions:
    #         canonical_id = cluster["canonical_id"]
    #         canonical_type = cluster["canonical_type"]
    #         canonical_mention = mention_id_map[canonical_id]
    #         if canonical_mention.type == AnnotationTypes.TOKEN:
    #             continue
    #
    #         canonical_mention.value = canonical_type
    #
    #         for mention in cluster["mentions"]:
    #             m_id = mention["id"]
    #             if canonical_id == m_id:
    #                 continue
    #
    #             mention = mention_id_map[m_id]
    #             if mention.type == AnnotationTypes.TOKEN:
    #                 document.text.add_annotation(
    #                     text=mention.text,
    #                     start=mention.start,
    #                     end=mention.end,
    #                     sentence_id=mention.sentence_id,
    #                     type="entity",
    #                     value=canonical_type,
    #                     source="coref",
    #                     embedding=mention.embedding,
    #                     metadata={
    #                         Metadata.COREF: canonical_mention.id,
    #                         Metadata.COREF_TEXT: canonical_mention.normalized_text,
    #                     },
    #                 )
    #             else:
    #                 mention.value = canonical_type
    #                 mention[Metadata.COREF] = canonical_mention.id
    #                 mention[Metadata.COREF_TEXT] = canonical_mention.normalized_text
    #
    #     document.text.clear_cache()


_coref: InDocumentCoref | None = None
_lock = threading.Lock()


def get_in_document_coref_model():
    global _coref
    _lock.acquire()
    try:
        if _coref is None:
            _coref = InDocumentCoref.load_coref_model(device="cpu")
        return _coref
    finally:
        _lock.release()
