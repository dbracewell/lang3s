from typing import Optional

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
        lstm_hidden_dim: int,
        num_labels: int,
        num_lstm_layers: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()

        from torchcrf import CRF  # local import to avoid hard dep at top if desired

        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=lstm_hidden_dim,
            num_layers=num_lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_lstm_layers > 1 else 0.0,
        )

        self.dropout = nn.Dropout(dropout)
        self.hidden2tag = nn.Linear(lstm_hidden_dim * 2, num_labels)

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
            return emissions, -log_likelihood  # return loss

        # Inference: returns best path (list of list of ints)
        best_paths = self.crf.decode(emissions, mask=mask)
        return best_paths
