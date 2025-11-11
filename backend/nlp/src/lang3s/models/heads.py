import math
from typing import Optional

import torch.nn as nn
import torch.nn.functional as F
from torchcrf import CRF

from .types import TaskType


class LowRankAdapter(nn.Module):
    def __init__(self, hidden_size, rank=8, dropout=0.1):
        super().__init__()
        self.rank = rank
        self.down_proj = nn.Linear(hidden_size, rank, bias=False)
        self.up_proj = nn.Linear(rank, hidden_size, bias=False)
        self.dropout = nn.Dropout(dropout)
        nn.init.zeros_(self.up_proj.weight)
        nn.init.kaiming_uniform_(self.down_proj.weight, a=math.sqrt(5))

    def forward(self, x):
        return x + self.dropout(self.up_proj(self.down_proj(x)))


class TaskHead(nn.Module):
    def __init__(
        self,
        hidden_size: int,
        num_labels: int,
        task_type: TaskType,
        lstm_hidden: Optional[int] = None,
    ):
        super().__init__()
        self.task_type = task_type
        self.num_labels = num_labels
        self.adapter = LowRankAdapter(hidden_size)

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
            self.dropout = nn.Dropout(0.2)
            self.classifier = nn.Linear(lstm_out_dim, num_labels)
            self.crf = CRF(num_labels, batch_first=True)

        else:
            self.classifier = nn.Linear(hidden_size, num_labels)
            self.lstm = None
            self.crf = None

        nn.init.xavier_uniform_(self.classifier.weight)
        nn.init.zeros_(self.classifier.bias)

    def forward(self, hidden, mask=None, labels=None):
        adapted = self.adapter(hidden)

        if self.task_type == TaskType.SENTENCE:
            if mask is not None:
                mask = mask.unsqueeze(-1).float()
                pooled = (adapted * mask).sum(dim=1) / mask.sum(dim=1).clamp(
                    min=1e-6
                )
            else:
                pooled = adapted.mean(dim=1)

            logits = self.classifier(pooled)
            loss = None
            if labels is not None:
                loss = F.cross_entropy(logits, labels)

            return logits, loss

        hidden_out, _ = self.lstm(adapted)  # type: ignore
        logits = self.classifier(self.dropout(hidden_out))

        loss = None
        if labels is not None:
            if mask is None:
                mask = labels != -100
            mask[:, 0] = True

            crf_loss = -self.crf(logits, labels, mask=mask, reduction="mean")  # type: ignore
            return logits, crf_loss

        else:
            return self.crf.decode(logits, mask=mask)  # type: ignore
