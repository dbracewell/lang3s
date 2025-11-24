from typing import Dict, Optional

import torch
from torch import nn


def parse_bio(tag: str):
    """Return prefix ('B','I','O') and chunk_type (or None)."""
    if tag == "O":
        return "O", None
    if "-" not in tag:
        return "O", None
    prefix, chunk_type = tag.split("-", 1)
    return prefix, chunk_type


def build_illegal_bio_transitions(label2id):
    illegal = []
    for from_tag, from_id in label2id.items():
        from_prefix, from_type = parse_bio(from_tag)
        for to_tag, to_id in label2id.items():
            to_prefix, to_type = parse_bio(to_tag)

            # 1. O cannot go to I-X
            if from_prefix == "O" and to_prefix == "I":
                illegal.append((from_id, to_id))

            # 2. B-X cannot go to I-Y unless types match
            if from_prefix == "B" and to_prefix == "I" and from_type != to_type:
                illegal.append((from_id, to_id))

            # 3. I-X cannot go to I-Y unless types match
            if from_prefix == "I" and to_prefix == "I" and from_type != to_type:
                illegal.append((from_id, to_id))
    return illegal


def apply_transition_constraints(crf, label2id):
    illegal = build_illegal_bio_transitions(label2id)

    # A huge negative value to kill probability
    NEG_INF = -1e4

    with torch.no_grad():
        for (from_tag, to_tag) in illegal:
            crf.transitions[from_tag, to_tag] = NEG_INF


class BiLSTMCRFClassifierHead(nn.Module):
    """
    A BiLSTM + Linear layer + CRF for token classification.

    Expects:
        token_embeddings: [B, T, H]
        mask: [B, T] boolean mask
        labels: [B, T] (optional during training)
    """

    def __init__(
        self,
        embedding_dim: int,
        hidden_size: int,
        num_labels: int,
        label2id: Dict[str, int],
        num_lstm_layers: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()

        from torchcrf import CRF  # local import to avoid hard dep at top if desired

        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_size,
            num_layers=num_lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_lstm_layers > 1 else 0.0,
        )

        self.dropout = nn.Dropout(dropout)
        self.hidden2tag = nn.Linear(hidden_size * 2, num_labels)

        # CRF expects emission scores [B, T, num_labels]
        self.crf = CRF(num_tags=num_labels, batch_first=True)
        # apply_transition_constraints(self.crf, label2id)

    def forward(
        self,
        token_embeddings: torch.Tensor,  # [B, T, H]
        mask: torch.ByteTensor,  # [B, T] bool
        labels: Optional[torch.Tensor] = None,  # [B, T]
    ):
        # BiLSTM
        lstm_out, _ = self.lstm(token_embeddings)  # [B, T, 2H]
        lstm_out = self.dropout(lstm_out)

        # Project to num_labels
        emissions = self.hidden2tag(lstm_out)  # [B, T, num_labels]

        if labels is not None:
            # CRF loss (negative log-likelihood)
            log_likelihood = self.crf(emissions, labels, mask=mask, reduction="mean")
            return -log_likelihood  # return loss

        # Inference: returns best path (list of list of ints)
        best_paths = self.crf.decode(emissions, mask=mask)
        return best_paths


from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
from torchcrf import CRF


# ---------------------------------------------------------
# Helpers for BIO constraints (optional)
# ---------------------------------------------------------

def _parse_bio(tag: str) -> Tuple[str, Optional[str]]:
    """
    Parse a BIO tag like 'B-NP', 'I-VP', 'O'.
    Returns (prefix, type) where type is None for 'O' or malformed.
    """
    if tag == "O" or tag == "":
        return "O", None
    if "-" not in tag:
        return "O", None
    prefix, chunk_type = tag.split("-", 1)
    return prefix, chunk_type


def _build_illegal_bio_transitions(label2id: Dict[str, int]) -> List[Tuple[int, int]]:
    """
    Build list of illegal transitions (from_id, to_id) for BIO tagging.

    Rules:
      1) O -> I-X is illegal
      2) B-X -> I-Y is illegal if X != Y
      3) I-X -> I-Y is illegal if X != Y
    """
    illegal: List[Tuple[int, int]] = []

    for from_tag, from_id in label2id.items():
        from_prefix, from_type = _parse_bio(from_tag)

        for to_tag, to_id in label2id.items():
            to_prefix, to_type = _parse_bio(to_tag)

            # 1. O -> I-X is illegal
            if from_prefix == "O" and to_prefix == "I":
                illegal.append((from_id, to_id))
                continue

            # 2. B-X -> I-Y is illegal if X != Y
            if from_prefix == "B" and to_prefix == "I" and from_type != to_type:
                illegal.append((from_id, to_id))
                continue

            # 3. I-X -> I-Y is illegal if X != Y
            if from_prefix == "I" and to_prefix == "I" and from_type != to_type:
                illegal.append((from_id, to_id))
                continue

    return illegal


def _apply_bio_constraints_to_crf(crf: CRF,
                                  label2id: Dict[str, int],
                                  neg_inf: float = -1e4) -> None:
    """
    Apply BIO legality constraints to a torchcrf.CRF instance
    by setting certain transitions to large negative values.
    """
    illegal = _build_illegal_bio_transitions(label2id)

    with torch.no_grad():
        for from_id, to_id in illegal:
            crf.transitions[from_id, to_id] = neg_inf


# ---------------------------------------------------------
# Multi-Sample Dropout (optional)
# ---------------------------------------------------------

class MultiSampleDropout(nn.Module):
    """
    Multi-sample dropout:
      - Apply dropout N times
      - Pass through the same FFN
      - Average the logits

    This tends to improve robustness on small or noisy datasets.
    """

    def __init__(self, base_module: nn.Module, p: float = 0.5, num_samples: int = 4):
        super().__init__()
        assert num_samples >= 1
        self.base_module = base_module
        self.num_samples = num_samples
        self.dropout_layers = nn.ModuleList(
            [nn.Dropout(p) for _ in range(num_samples)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.num_samples == 1 or not self.training:
            # At eval time, or if only 1 sample, just run base module once
            return self.base_module(x)

        logits_sum = 0.0
        for drop in self.dropout_layers:
            logits_sum = logits_sum + self.base_module(drop(x))

        return logits_sum / float(self.num_samples)


# ---------------------------------------------------------
# Generic Token Classification Head: BiLSTM + FFN + CRF
# ---------------------------------------------------------

class CRFTokenClassificationHead(nn.Module):
    """
    Generic token classification head with:
      - BiLSTM
      - (optional) LayerNorm
      - (optional) Residual connection from input embeddings
      - Feed-forward network with GELU
      - (optional) Multi-sample dropout
      - CRF with optional BIO legality constraints

    Expected inputs:
      token_embeddings: [B, T, H_in]
      mask:             [B, T] (bool)
      labels (optional): [B, T] (long), indices into label space

    Forward behavior:
      - If labels is provided: returns scalar loss
      - If labels is None: returns decoded paths (List[List[int]])
    """

    def __init__(
        self,
        embedding_dim: int,  # H_in from your encoder
        num_labels: int,
        hidden_size: int = 256,  # LSTM hidden size (per direction)
        num_lstm_layers: int = 1,
        ffn_hidden_size: int = 256,
        dropout: float = 0.1,
        num_msd_samples: int = 4,  # >1 enables multi-sample dropout
        use_layernorm: bool = True,
        use_residual: bool = True,
        use_bio_constraints: bool = False,
        label2id: Optional[Dict[str, int]] = None,
    ):
        super().__init__()

        self.embedding_dim = embedding_dim
        self.hidden_size = hidden_size
        self.num_labels = num_labels
        self.use_layernorm = use_layernorm
        self.use_residual = use_residual

        # ---------------- BiLSTM ----------------
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_size,
            num_layers=num_lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_lstm_layers > 1 else 0.0,
        )
        lstm_output_dim = hidden_size * 2

        # ---------------- LayerNorm ----------------
        self.layernorm = nn.LayerNorm(lstm_output_dim) if use_layernorm else None

        # ---------------- Residual projection ----------------
        # Project input embeddings to LSTM output dimension so we can add them
        if use_residual:
            self.residual_proj = nn.Linear(embedding_dim, lstm_output_dim)
        else:
            self.residual_proj = None

        # ---------------- Feed-forward head ----------------
        ffn = nn.Sequential(
            nn.Linear(lstm_output_dim, ffn_hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ffn_hidden_size, num_labels),
        )

        # Multi-sample dropout wrapper (optional)
        if num_msd_samples is not None and num_msd_samples > 1:
            self.ffn = MultiSampleDropout(
                base_module=ffn,
                p=dropout,
                num_samples=num_msd_samples,
            )
        else:
            self.ffn = ffn

        # ---------------- CRF ----------------
        self.crf = CRF(num_tags=num_labels, batch_first=True)

        # Optional BIO constraints
        if use_bio_constraints:
            if label2id is None:
                raise ValueError(
                    "use_bio_constraints=True requires label2id to be provided."
                )
            _apply_bio_constraints_to_crf(self.crf, label2id)

    def forward(
        self,
        token_embeddings: torch.Tensor,  # [B, T, H_in]
        mask: torch.ByteTensor,  # [B, T] (bool)
        labels: Optional[torch.Tensor] = None,  # [B, T] (long) or None
    ):
        """
        If labels is provided:
            returns scalar loss (negative log-likelihood).

        If labels is None:
            returns decoded paths (List[List[int]]) from CRF.
        """
        # ---------------- LSTM ----------------
        lstm_out, _ = self.lstm(token_embeddings)  # [B, T, 2*hidden]

        # ---------------- Residual + LayerNorm ----------------
        if self.residual_proj is not None:
            # Project original embeddings and add as residual
            residual = self.residual_proj(token_embeddings)
            lstm_out = lstm_out + residual

        if self.layernorm is not None:
            lstm_out = self.layernorm(lstm_out)

        # ---------------- Feed-forward → emissions ----------------
        emissions = self.ffn(lstm_out)  # [B, T, num_labels]

        # ---------------- CRF ----------------
        if labels is not None:
            # CRF expects mask as byte/bool
            # Negative log-likelihood (we return positive loss)
            log_likelihood = self.crf(emissions, labels, mask=mask, reduction="mean")
            return -log_likelihood

        # Decoding: returns List[List[int]] (per-sequence label IDs)
        best_paths = self.crf.decode(emissions, mask=mask)
        return best_paths
