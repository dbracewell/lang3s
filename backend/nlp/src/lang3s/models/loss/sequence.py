import torch
import torch.nn as nn


class TransitionPenaltyLoss(nn.Module):
    """
    Vectorized BIO transition penalty loss.
    Penalizes illegal transitions:
      O → I-X
      B-Y or I-Y → I-X where X != Y

    Extremely fast (no Python loops).
    """

    def __init__(self, idx2label, penalty=0.1):
        super().__init__()
        self.penalty = penalty

        # Precompute prefix and type ids
        prefixes = []
        types = []

        for lbl in idx2label.values():
            if lbl == "O":
                prefixes.append(0)  # O
                types.append(-1)
            else:
                p, t = lbl.split("-")
                prefixes.append(1 if p == "B" else 2)  # B=1, I=2
                types.append(hash(t) % 997)  # stable small bucket

        self.register_buffer("prefix_ids", torch.tensor(prefixes))  # (C,)
        self.register_buffer("type_ids", torch.tensor(types))  # (C,)

    def forward(self, logits, mask):
        """
        logits: (B, T, C)
        mask  : (B, T) boolean (valid locations)
        """

        B, T, C = logits.shape

        # argmax predictions
        pred = logits.argmax(dim=-1)  # (B, T)

        # Shifted predictions for prev/curr pairs
        prev = pred[:, :-1]  # (B, T-1)
        curr = pred[:, 1:]  # (B, T-1)

        valid = mask[:, 1:]  # ignore t=0 and masked positions

        # prefix and type lookup (vectorized)
        prev_prefix = self.prefix_ids[prev]  # type: ignore (B, T-1)
        curr_prefix = self.prefix_ids[curr]  # type: ignore (B, T-1)

        prev_type = self.type_ids[prev]  # type: ignore (B, T-1)
        curr_type = self.type_ids[curr]  # type: ignore (B, T-1)

        # illegal if curr_prefix == I
        curr_is_I = (curr_prefix == 2)

        # prev = O  (prefix 0)  ⇒ O → I-X illegal
        prev_is_O = (prev_prefix == 0)

        illegal_O_to_I = curr_is_I & prev_is_O

        # illegal type mismatch: prev in B/I but type differs
        prev_is_B_or_I = (prev_prefix == 1) | (prev_prefix == 2)
        type_mismatch = (prev_type != curr_type)

        illegal_type = curr_is_I & prev_is_B_or_I & type_mismatch

        # combine both
        illegal = (illegal_O_to_I | illegal_type) & valid

        num_illegal = illegal.sum()
        total_pairs = valid.sum().clamp(min=1)

        penalty_value = self.penalty * (num_illegal.float() / total_pairs.float())

        return penalty_value
