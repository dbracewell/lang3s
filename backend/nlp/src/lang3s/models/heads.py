import math
from typing import Optional, cast

import numpy as np
import torch
import torch.nn as nn
from torch import Tensor
from torchcrf import CRF

from .types import TaskType


class LowRankAdapter(nn.Module):
    def __init__(self, hidden_size, rank=16, dropout=0.1):
        super().__init__()
        self.rank = rank
        self.adapter = nn.Sequential(
            nn.Linear(hidden_size, rank, bias=False),
            nn.ReLU(),
            nn.Linear(rank, hidden_size, bias=False),
            nn.Dropout(dropout),
        )
        nn.init.zeros_(cast(Tensor, self.adapter[0].weight))
        nn.init.kaiming_uniform_(cast(Tensor, self.adapter[2].weight), a=math.sqrt(5))

    def forward(self, x):
        return x + self.adapter(x)


def mixup_data(x, y, alpha=0.2):
    """Returns mixed inputs, pairs of targets, and lambda"""
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1.0

    batch_size = x.size(0)
    index = torch.randperm(batch_size).to(x.device)

    mixed_x = lam * x + (1 - lam) * x[index, :]
    y_a, y_b = y, y[index]
    return mixed_x, y_a, y_b, lam


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


class TaskHead(nn.Module):
    def __init__(
        self,
        hidden_size: int,
        num_labels: int,
        task_type: TaskType,
        dropout: float = 0.1,
        lstm_hidden: Optional[int] = None,
    ):
        super().__init__()
        self.task_type = task_type
        self.num_labels = num_labels
        self.adapter = LowRankAdapter(hidden_size, dropout=dropout)
        self.dropout = nn.Dropout(dropout)

        if task_type == TaskType.TOKEN:
            self.lstm_hidden = lstm_hidden or hidden_size // 2
            self.lstm = nn.LSTM(
                input_size=hidden_size,
                hidden_size=self.lstm_hidden,
                num_layers=1,
                bidirectional=True,
                batch_first=True,
            )
            lstm_out_dim = self.lstm_hidden * 2
            self.classifier = nn.Linear(lstm_out_dim, num_labels)
            self.crf = CRF(num_labels, batch_first=True)

        else:
            self.classifier = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size // 2, num_labels)
            )
            self.lstm = None
            self.crf = None

        self._init_weights()

    def _init_weights(self):
        for module in self.classifier.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)

    def forward(self, hidden, mask=None, labels=None):
        adapted = self.adapter(hidden)

        if self.task_type.is_sentence_level():
            if mask is not None:
                mask = mask.unsqueeze(-1).float()
                summed = torch.sum(adapted * mask, dim=1)
                counts = torch.clamp(mask.sum(dim=1), min=1e-9)
                pooled = summed / counts
            else:
                pooled = adapted.mean(dim=1)

            if self.training:
                pooled, y_a, y_b, lam = mixup_data(pooled, labels, alpha=0.4)
                logits = self.classifier(self.dropout(pooled))
                if self.task_type == TaskType.SENTENCE_MULTILABEL:
                    loss_fn = nn.BCEWithLogitsLoss()
                    loss = mixup_criterion(loss_fn, logits, y_a, y_b, lam)
                    # labels = labels.float()
                    # loss = loss_fn(logits, labels)
                else:
                    loss_fn = nn.CrossEntropyLoss()
                    loss = mixup_criterion(loss_fn, logits, y_a, y_b, lam)
                return logits, loss
            else:
                logits = self.classifier(self.dropout(pooled))
                if self.task_type == TaskType.SENTENCE_MULTILABEL:
                    probs = torch.sigmoid(logits)
                    preds = (probs > 0.5).int()
                else:
                    preds = torch.argmax(logits, dim=-1)
                return preds

        elif self.task_type.is_token():
            hidden_out, _ = self.lstm(adapted)  # type: ignore
            logits = self.classifier(self.dropout(hidden_out))
            if self.training:
                if mask is None:
                    mask = labels != -100
                mask[:, 0] = True
                crf_loss = -self.crf(logits, labels, mask=mask, reduction="mean")  # type: ignore
                return logits, crf_loss
            else:
                return self.crf.decode(logits, mask=mask)  # type: ignore

        else:
            raise ValueError("Task type not supported")
