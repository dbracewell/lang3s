from typing import Optional

from torch import nn
from torchcrf import CRF


class BiLSTMCRFClassifierHead(nn.Module):
    """
    Implements a Bidirectional LSTM with a CRF layer for sequence labeling tasks.

    This class is designed for tasks such as Named Entity Recognition (NER),
    where a combination of BiLSTM and CRF can improve the accuracy by modeling
    sequential dependencies in the labels. It integrates a bidirectional LSTM
    layer for feature extraction, followed by a classification head and a CRF layer
    to enforce valid label transitions and improve output sequence quality.

    Attributes:
        hidden_size (int): Defines the size of the input feature vectors.
        num_labels (int): Specifies the number of distinct output labels.
        dropout (nn.Dropout): Dropout layer to prevent overfitting.
        lstm_hidden (int): Number of hidden units in the LSTM layer. If not provided,
            defaults to half of `hidden_size`.
        lstm (nn.LSTM): Single-layer bidirectional LSTM for feature extraction.
        classifier (nn.Linear): Linear layer maps LSTM output features to
            label logits.
        crf (CRF): Conditional Random Field layer to output valid sequences and
            optimize sequence-level accuracy.

    Methods:
        forward(hidden, mask=None, labels=None):
            Performs the forward pass through the BiLSTM, classifier, and CRF layers.

            Args:
                hidden (Tensor): Input feature representation of shape
                    (batch_size, sequence_length, hidden_size).
                mask (Tensor, optional): Binary mask tensor of shape
                    (batch_size, sequence_length) indicating which tokens are
                    valid. Defaults to None.
                labels (Tensor, optional): Ground truth labels of shape
                    (batch_size, sequence_length) for calculating the CRF loss.
                    Defaults to None.

            Returns:
                Tuple[Tensor, Tensor]: If `labels` is provided, returns a tuple containing
                    the logits tensor of shape
                    (batch_size, sequence_length, num_labels) and the scalar CRF loss.
                    Otherwise, returns the predicted label sequences as a list
                    of lists.
    """

    def __init__(self,
                 hidden_size: int,
                 num_labels: int,
                 dropout: float = 0.2,
                 lstm_hidden: Optional[int] = None):
        super(BiLSTMCRFClassifierHead, self).__init__()
        self.hidden_size = hidden_size
        self.dropout = nn.Dropout(dropout)
        self.num_labels = num_labels
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

    def forward(self, hidden, mask=None, labels=None):
        hidden_out, _ = self.lstm(hidden)  # type: ignore
        logits = self.classifier(self.dropout(hidden_out))
        if labels is not None:
            if mask is None:
                mask = labels != -100
            mask[:, 0] = True
            crf_loss = -self.crf(logits, labels, mask=mask, reduction="mean")  # type: ignore
            return logits, crf_loss
        else:
            return self.crf.decode(logits, mask=mask)  # type: ignore
