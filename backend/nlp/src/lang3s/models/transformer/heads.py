from typing import Dict, Optional

import torch
import torch.nn as nn
from torch.nn.modules.activation import MultiheadAttention

from lang3s.models.augmentation.mixup import Mixup
from lang3s.models.layers.adapter import DoRA
from lang3s.models.layers.crf import BiLSTMCRFClassifierHead
from lang3s.models.layers.mlp import MLPClassificationHead
from lang3s.models.loss.focal import FocalLoss
from .shared_types import TaskType


class SentenceClassificationHead(nn.Module):

    def __init__(self,
                 task_type: TaskType,
                 hidden_size: int,
                 num_labels: int,
                 original_layer: nn.Linear,
                 rank: int = 8,
                 alpha: int = 8,
                 mixup_alpha: float = 0.2,
                 use_mixup: bool = False,
                 weights: Optional[torch.Tensor] = None,
                 use_focal_loss: bool = False,
                 num_attention_heads: int = 0,
                 use_dora: bool = False,
                 **kwargs
                 ):
        super(SentenceClassificationHead, self).__init__()
        self.task_type = task_type
        self.num_attention_heads: int = num_attention_heads
        self.use_dora = use_dora
        self.mixup_alpha = mixup_alpha
        self.mixup = None
        self.attention_layer = None

        if self.use_dora and original_layer is not None:
            self.dora_adapter = DoRA(original_layer=original_layer,
                                     rank=rank,
                                     alpha=alpha)

        if self.num_attention_heads > 0:
            self.attention_layer = MultiheadAttention(hidden_size,
                                                      num_heads=num_attention_heads,
                                                      batch_first=True)

        loss_type = "multiclass" if self.task_type == TaskType.SENTENCE else "multilabel"
        if use_focal_loss:
            loss_function = FocalLoss(alpha=weights,
                                      loss_type=loss_type,
                                      reduction="mean")
        elif self.task_type == TaskType.SENTENCE:
            loss_function = nn.CrossEntropyLoss()
        else:
            loss_function = nn.BCEWithLogitsLoss()

        if use_mixup:
            self.mixup = Mixup(alpha=self.mixup_alpha, loss_fn=loss_function)

        self.classifier = MLPClassificationHead(
            hidden=hidden_size,
            num_labels=num_labels,
            loss_fn=loss_function,
        )

    def forward(self, hidden, mask=None, labels=None, return_logits=False):
        x = hidden

        if self.attention_layer is not None and x.dim() == 3:
            key_padding_mask = None
            if mask is not None:
                key_padding_mask = ~mask
            attn_out, _ = self.attention_layer(
                x, x, x,
                key_padding_mask=key_padding_mask,
                need_weights=False,
            )
            pooled = attn_out.mean(dim=1)

        else:
            if x.dim() == 3:
                pooled = x.mean(dim=1)
            else:
                pooled = x

        if self.dora_adapter is not None:
            pooled = self.dora_adapter(pooled)

        if labels is not None:
            if self.mixup is not None:
                pooled, y_a, y_b, lam = self.mixup.augment(pooled, labels)
                logits = self.classifier(pooled)
                loss = self.mixup(logits, y_a, y_b, lam)
                return logits, loss

            return self.classifier(pooled, labels)
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

    def __init__(self,
                 hidden_size: int,
                 num_labels: int,
                 label2id: Dict[str, int],
                 dropout=0.2,
                 lstm_hidden: int = 256,
                 **kwargs
                 ):
        super(TokenClassificationHead, self).__init__()
        self.task_type = TaskType.TOKEN
        # self.classifier = CRFTokenClassificationHead(
        #     embedding_dim=hidden_size,
        #     num_labels=num_labels,
        #     dropout=dropout,
        #     hidden_size=lstm_hidden,
        #     label2id=label2id,
        #     use_bio_constraints=True,
        # )
        self.classifier = BiLSTMCRFClassifierHead(
            hidden_size=lstm_hidden,
            num_labels=num_labels,
            dropout=dropout,
            embedding_dim=hidden_size,
            label2id=label2id,
        )

    def forward(self, hidden, mask=None, labels=None, return_logits=False):
        return self.classifier(hidden, mask=mask, labels=labels)
