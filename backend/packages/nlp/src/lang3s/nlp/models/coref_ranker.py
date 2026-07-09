from typing import Any

import numpy as np
import torch
import torch.nn as nn

from lang3s.core import config
from lang3s.data.db import get_ontology
from lang3s.data.schemas import Metadata, Ontology, TextAnnotation

POS_MAP = {
    "ADJ": 1,
    "ADP": 2,
    "ADV": 3,
    "AUX": 4,
    "CCONJ": 5,
    "DET": 6,
    "INTJ": 7,
    "NOUN": 8,
    "NUM": 9,
    "PART": 10,
    "PRON": 11,
    "PROPN": 12,
    "PUNCT": 13,
    "SCONJ": 14,
    "SYM": 15,
    "VERB": 16,
    "X": 17,
}

REVERSE_POS_MAP = {v: k for k, v in POS_MAP.items()}

NER_MAP = {
    "person": 1,
    "organization": 2,
    "geo_political_entity": 3,
    "location": 4,
    "facility": 5,
    "product": 6,
}

GENDER_ANIMACY_MAP = {
    "Masc": 1,  # Male (Animate)
    "Fem": 2,  # Female (Animate)
    "Neut": 3,  # Inanimate (It, Orgs, Locations)
    "Plur": 4,  # Plural (They, Them)
}


def create_coref_mention(annotation: TextAnnotation):
    embedding = annotation.embedding
    if embedding is None:
        embedding = np.mean([t.embedding for t in annotation.tokens])
    mention: dict[str, Any] = {
        "emb": torch.from_numpy(embedding),
        "text": annotation.content,
        "id": annotation.id,
        "type": annotation.type_,
        "cleaned": annotation.to_string(
            ignore_stopwords=True,
            lemmatize=False,
            lowercase=False,
        ),
        "value": annotation.value if annotation.type_ == "entity" else "",
    }

    head = annotation.head
    mention["pos_idx"] = POS_MAP.get(head.value, 0)

    ont_type = ""
    if annotation.type_ == "entity":
        ont_type = get_ontology().get_ontology_concept_for_mapping(annotation.mapping)
        if not ont_type:
            ont_type = ""
    ont_type = ont_type.lower()

    mention["ner_idx"] = 0
    for otype, index in NER_MAP.items():
        if Ontology.is_ontology_type(ont_type, otype):
            mention["ner_idx"] = index
            break

    gender = head.get(Metadata.GENDER, None)
    number = head.get(Metadata.NUMBER, None)
    mention["gender_idx"] = 0

    if gender:
        mention["gender_idx"] = GENDER_ANIMACY_MAP.get(gender, 0)  # type:ignore
    elif number and number == "Plur":
        mention["gender_idx"] = GENDER_ANIMACY_MAP["Plur"]
    else:
        if mention["ner_idx"] == 1:
            mention["gender_idx"] = 0
        elif mention["ner_idx"] in [2, 3, 4, 5, 6]:
            mention["gender_idx"] = GENDER_ANIMACY_MAP["Neut"]
        elif head.value == "NOUN":
            mention["gender_idx"] = GENDER_ANIMACY_MAP["Neut"]
        else:
            mention["gender_idx"] = 0

    return mention


class FastCorefRanker(nn.Module):
    def __init__(
        self,
        embedding_dim=config.SEMANTIC_EMBEDDING_DIMENSION,
        hidden_dim=1024,
        meta_dim=16,
        max_distance_bins=10,
        device="cpu",
    ):
        super().__init__()
        num_pos_tags = len(POS_MAP) + 1
        num_ner_tags = len(NER_MAP) + 1
        num_gender_tags = len(GENDER_ANIMACY_MAP) + 1
        self.device = device

        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.max_distance_bins = max_distance_bins

        self.pos_embeddings = nn.Embedding(num_pos_tags, meta_dim)
        self.ner_embeddings = nn.Embedding(num_ner_tags, meta_dim)
        self.gender_embeddings = nn.Embedding(num_gender_tags, meta_dim)

        input_dim = (embedding_dim * 3) + max_distance_bins + (meta_dim * 6) + 3

        self.scorer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

        self.dummy_score = nn.Parameter(torch.tensor([0.0]))
        self.distance_embeddings = nn.Embedding(max_distance_bins, max_distance_bins)
        self.distance_embeddings.weight.data.copy_(torch.eye(max_distance_bins))
        self.distance_embeddings.weight.requires_grad = False

        self.to(device)

    def forward(self, mention, candidates, distances):
        """
        mention: dict containing 'emb', 'pos_idx', 'ner_idx', 'gender_idx'
        candidates: list of dicts with the same keys
        """
        num_cands = len(candidates)

        # Stack all the text embeddings
        cand_embs = torch.stack([c["emb"] for c in candidates])
        ment_emb_repeated = mention["emb"].unsqueeze(0).expand(num_cands, -1)

        # Get Metadata Embeddings for the current Mention
        m_pos = torch.tensor([mention["pos_idx"]] * num_cands, device=self.device)
        m_ner = torch.tensor([mention["ner_idx"]] * num_cands, device=self.device)
        m_gen = torch.tensor([mention["gender_idx"]] * num_cands, device=self.device)

        # Get Metadata Embeddings for the Candidates
        c_pos = torch.tensor([c["pos_idx"] for c in candidates], device=self.device)
        c_ner = torch.tensor([c["ner_idx"] for c in candidates], device=self.device)
        c_gen = torch.tensor([c["gender_idx"] for c in candidates], device=self.device)

        ment_pos = self.pos_embeddings(m_pos)
        ment_ner = self.ner_embeddings(m_ner)
        ment_gen = self.gender_embeddings(m_gen)

        cand_pos = self.pos_embeddings(c_pos)
        cand_ner = self.ner_embeddings(c_ner)
        cand_gen = self.gender_embeddings(c_gen)

        similarity = ment_emb_repeated * cand_embs
        dist_feats = self.distance_embeddings(distances)

        # .float().unsqueeze(1) turns the True/False arrays into [num_cands, 1] columns
        same_gender = ((c_gen == m_gen) & (m_gen != 0)).float().unsqueeze(1)
        same_ner = ((c_ner == m_ner) & (m_ner != 0)).float().unsqueeze(1)

        # 1.0 if comparing a NOUN (8) to a PROPN (12)
        is_nominal_pair = (
            (((m_pos == 8) & (c_pos == 12)) | ((m_pos == 12) & (c_pos == 8)))
            .float()
            .unsqueeze(1)
        )

        pair_reps = torch.cat(
            [
                ment_emb_repeated,
                cand_embs,
                similarity,
                dist_feats,
                ment_pos,
                cand_pos,
                ment_ner,
                cand_ner,
                ment_gen,
                cand_gen,
                same_gender,
                same_ner,
                is_nominal_pair,
            ],
            dim=1,
        )

        candidate_scores = self.scorer(pair_reps).squeeze(-1)

        m_gen = mention["gender_idx"]
        c_gens = torch.tensor([c["gender_idx"] for c in candidates], device=self.device)
        gender_clash = ((m_gen == 1) & (c_gens == 2)) | ((m_gen == 2) & (c_gens == 1))
        animacy_clash = ((m_gen == 1) | (m_gen == 2)) & (c_gens == 3)
        animacy_clash_rev = (m_gen == 3) & ((c_gens == 1) | (c_gens == 2))

        invalid_pairs = gender_clash | animacy_clash | animacy_clash_rev
        candidate_scores = candidate_scores.masked_fill(invalid_pairs, -1e4)
        all_scores = torch.cat([self.dummy_score, candidate_scores])

        return all_scores

    def batch_predict(self, m_dict, c_dict, distances):
        """
        Accepts flattened tensors of shape [Total_Pairs] and processes
        the entire document in a single O(1) GPU pass.
        """
        # 1. Semantic Similarity
        similarity = m_dict["emb"] * c_dict["emb"]
        dist_feats = self.distance_embeddings(distances)

        # 2. Metadata Embeddings
        ment_pos = self.pos_embeddings(m_dict["pos_idx"])
        ment_ner = self.ner_embeddings(m_dict["ner_idx"])
        ment_gen = self.gender_embeddings(m_dict["gender_idx"])

        cand_pos = self.pos_embeddings(c_dict["pos_idx"])
        cand_ner = self.ner_embeddings(c_dict["ner_idx"])
        cand_gen = self.gender_embeddings(c_dict["gender_idx"])

        # 3. Boolean Flags (Shape: [Total_Pairs, 1])
        same_gender = (
            (
                (c_dict["gender_idx"] == m_dict["gender_idx"])
                & (m_dict["gender_idx"] != 0)
            )
            .float()
            .unsqueeze(1)
        )
        same_ner = (
            ((c_dict["ner_idx"] == m_dict["ner_idx"]) & (m_dict["ner_idx"] != 0))
            .float()
            .unsqueeze(1)
        )

        m_pos = m_dict["pos_idx"]
        c_pos = c_dict["pos_idx"]
        is_nominal_pair = (
            (((m_pos == 8) & (c_pos == 12)) | ((m_pos == 12) & (c_pos == 8)))
            .float()
            .unsqueeze(1)
        )

        # 4. Concatenate and Score
        pair_reps = torch.cat(
            [
                m_dict["emb"],
                c_dict["emb"],
                similarity,
                dist_feats,
                ment_pos,
                cand_pos,
                ment_ner,
                cand_ner,
                ment_gen,
                cand_gen,
                same_gender,
                same_ner,
                is_nominal_pair,
            ],
            dim=1,
        )

        candidate_scores = self.scorer(pair_reps).squeeze(-1)

        # 5. The Hard Masks
        m_gen = m_dict["gender_idx"]
        c_gen = c_dict["gender_idx"]

        gender_clash = ((m_gen == 1) & (c_gen == 2)) | ((m_gen == 2) & (c_gen == 1))
        animacy_clash = ((m_gen == 1) | (m_gen == 2)) & (c_gen == 3)
        animacy_clash_rev = (m_gen == 3) & ((c_gen == 1) | (c_gen == 2))

        invalid_pairs = gender_clash | animacy_clash | animacy_clash_rev
        candidate_scores = candidate_scores.masked_fill(invalid_pairs, -1e4)

        return candidate_scores
