from torch import nn
from torch.nn import init


class MLPClassificationHead(nn.Module):
    """
    MLPClassificationHead is a neural network module for classification tasks.

    This class defines a multi-layer structure designed to perform sequential
    transformations on an input tensor, ultimately reducing its dimensions to
    match the number of target labels for classification. It employs normalization,
    dropout layers, activation functions, and linear transformations in a
    sequential manner to produce the final output.

    Attributes
    ----------
    net : nn.Sequential
        A sequential container of layers including LayerNorm, Dropout, Linear,
        and activation functions. This defines the architecture of the
        classification head.

    Methods
    -------
    forward(x)
        Performs the forward pass through the MLP

        Args:
            x (Tensor): Input feature representation of shape
                (batch_size, sequence_length, hidden_size).
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

    def __init__(self, hidden: int, num_labels: int, dropout=0.3):
        super(MLPClassificationHead, self).__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden // 2, num_labels),
        )
        self.__init_weights()

    def __init_weights(self):
        for m in self.net.modules():
            if isinstance(m, nn.Linear):
                init.kaiming_uniform_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    init.constant_(m.bias, 0)

    def forward(self, x):
        return self.net(x)
