from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.modules.activation import MultiheadAttention

from lang3s.ml.augmentation.mixup import Mixup
from lang3s.ml.layers.adapter import (
    DoRAActivationAdapter,
    ParallelLoRAAndDoRAActivationAdapterForSequence,
)
from lang3s.ml.layers.attention import FastLocalWindowAttention
from lang3s.ml.layers.mlp import MLPClassificationHead
from lang3s.ml.loss.focal import FocalLoss

from .typedefs import TaskType


class SentenceClassificationHead(nn.Module):
    def __init__(
        self,
        task_type: TaskType,
        hidden_size: int,
        num_labels: int,
        dora_rank: int = 8,
        lora_rank: int = 8,
        mixup_alpha: float = 0.2,
        use_mixup: bool = False,
        weights: Optional[torch.Tensor] = None,
        use_focal_loss: bool = False,
        num_attention_heads: int = 0,
        use_adapter: bool = False,
        dropout: float = 0.15,
        **kwargs,
    ):
        super(SentenceClassificationHead, self).__init__()
        self.task_type = task_type
        self.num_attention_heads: int = num_attention_heads
        self.use_adapter = use_adapter
        self.mixup_alpha = mixup_alpha
        self.mixup = None
        self.attention_layer = None
        self.dora_adapter = None
        self.dropout = nn.Dropout(dropout)

        if self.use_adapter:
            if self.num_attention_heads > 0:
                self.dora_adapter = ParallelLoRAAndDoRAActivationAdapterForSequence(
                    hidden_size=hidden_size, rank_dora=dora_rank, rank_lora=lora_rank
                )
            else:
                self.dora_adapter = DoRAActivationAdapter(
                    hidden_size=hidden_size, rank=dora_rank
                )

        if self.num_attention_heads > 0:
            self.attention_layer = MultiheadAttention(
                hidden_size, num_heads=num_attention_heads, batch_first=True
            )

        loss_type = (
            "multiclass" if self.task_type == TaskType.SENTENCE else "multilabel"
        )
        if use_focal_loss and weights is not None:
            self.loss_function = FocalLoss(
                alpha=weights,
                loss_type=loss_type,
                reduction="mean",
            )
        elif self.task_type == TaskType.SENTENCE:
            self.loss_function = nn.CrossEntropyLoss()
        else:
            self.loss_function = nn.BCEWithLogitsLoss()

        if use_mixup:
            self.mixup = Mixup(alpha=self.mixup_alpha, loss_fn=self.loss_function)

        self.classifier = MLPClassificationHead(
            hidden=hidden_size,
            num_labels=num_labels,
        )

    def forward(self, hidden, mask=None, labels=None, return_logits=False):
        x = hidden

        if self.dora_adapter is not None:
            x = self.dora_adapter(x)

        if self.attention_layer is not None and x.dim() == 3:
            key_padding_mask = None
            if mask is not None:
                key_padding_mask = ~mask.bool()

            attn_out, _ = self.attention_layer(
                x,
                x,
                x,
                key_padding_mask=key_padding_mask,
                need_weights=False,
            )
            pooled = attn_out.mean(dim=1)
        else:
            if x.dim() == 3:
                pooled = x.mean(dim=1)
            else:
                pooled = x

        pooled = self.dropout(pooled)

        if labels is not None:
            if self.mixup is not None:
                pooled, y_a, y_b, lam = self.mixup.augment(pooled, labels)
                logits = self.classifier(pooled)
                loss = self.mixup(logits, y_a, y_b, lam)
                return logits, loss

            logits = self.classifier(pooled)
            loss = self.loss_function(logits, labels)
            return logits, loss
        else:
            logits = self.classifier(pooled)
            if return_logits:
                return logits

            if self.task_type == TaskType.SENTENCE_MULTILABEL:
                probs = torch.sigmoid(logits)
                return (probs > 0.5).int()
            else:
                return torch.argmax(logits, dim=-1)


class TokenClassificationHead(nn.Module):
    def __init__(
        self,
        hidden_size: int,
        num_labels: int,
        dora_rank: int = 8,
        lora_rank: int = 8,
        num_attention_heads: int = 0,
        use_adapter: bool = False,
        dropout: float = 0.15,
        window_radius: int = 2,
        weights: Optional[torch.Tensor] = None,
        **kwargs,
    ):
        super(TokenClassificationHead, self).__init__()
        self.task_type = TaskType.TOKEN
        self.num_labels = num_labels
        self.attention_layer = None
        self.weights = weights
        self.dropout = nn.Dropout(dropout)

        if use_adapter:
            self.dora_adapter = ParallelLoRAAndDoRAActivationAdapterForSequence(
                hidden_size=hidden_size, rank_lora=lora_rank, rank_dora=dora_rank
            )
        else:
            self.dora_adapter = nn.Identity()

        if num_attention_heads > 0:
            self.attention_layer = FastLocalWindowAttention(
                hidden_size=hidden_size,
                window_radius=window_radius,
                num_heads=num_attention_heads,
                dropout=dropout,
            )

        self.classifier = MLPClassificationHead(
            num_labels=num_labels, hidden=hidden_size
        )

    def forward(self, hidden, mask, labels=None, return_logits=False):

        if mask is None:
            raise ValueError("Mask is required for token classification")

        x = self.dora_adapter(hidden)  # (B, T, H)

        if self.attention_layer is not None:
            attn_out = self.attention_layer(x, mask=mask)
        else:
            attn_out = x

        attn_out = self.dropout(attn_out)
        logits = self.classifier(attn_out)  # (B, T, C)

        pred_ids = logits.argmax(dim=-1)  # (B, T)
        best_paths = [p[m.bool()].tolist() for p, m in zip(pred_ids, mask)]

        if labels is not None:
            loss = F.cross_entropy(
                logits.view(-1, self.num_labels),  # (B*T, C)
                labels.view(-1),  # (B*T)
                ignore_index=-100,
                weight=self.weights,
            )
            if return_logits:
                return logits, loss

            return best_paths, loss

        if return_logits:
            return logits

        return best_paths
