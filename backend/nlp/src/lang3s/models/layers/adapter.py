import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class LoRABottleneck(nn.Module):
    def __init__(self,
                 hidden_size: int,
                 rank: int = 8,
                 dropout: float = 0.1,
                 alpha: int = 8):
        super(LoRABottleneck, self).__init__()
        self.rank = rank
        self.alpha = alpha
        self.scaling = self.alpha / self.rank

        # W_A (Down-projection: hidden_size -> rank)
        linear_down = nn.Linear(hidden_size, rank, bias=False)
        # W_B (Up-projection: rank -> hidden_size)
        linear_up = nn.Linear(rank, hidden_size, bias=False)

        self.adapter = nn.Sequential(
            linear_down,
            nn.Dropout(dropout),
            linear_up,
        )

        nn.init.kaiming_uniform_(linear_down.weight, a=math.sqrt(5))
        nn.init.zeros_(linear_up.weight)

    def forward(self, x):
        return x + self.scaling * self.adapter(x)


class LoRA(nn.Module):
    """
    A Parameter-Efficient Fine-Tuning (PEFT) module that implements the LoRA
    (Low-Rank Adaptation) technique by augmenting an existing nn.Linear layer.

    The forward pass computes: W_original @ x + (B @ A @ x) * (alpha / rank)
    """

    def __init__(
        self,
        original_layer: nn.Linear,
        rank: int = 8,
        alpha: int = 8,
        device: Optional[torch.device] = None,
    ):
        super().__init__()

        self.rank = rank
        self.scaling = alpha / rank
        self.in_features = original_layer.in_features
        self.out_features = original_layer.out_features
        self.has_bias = original_layer.bias is not None

        self.register_buffer(
            'original_weight',
            original_layer.weight.data.to(device) if device else original_layer.weight.data,
            persistent=True
        )

        if self.has_bias:
            self.register_buffer(
                'original_bias',
                original_layer.bias.data.to(device) if device else original_layer.bias.data,
                persistent=True
            )
        else:
            self.register_buffer('original_bias', None, persistent=True)

        self.lora_A = nn.Parameter(torch.empty(rank, self.in_features, device=device))
        self.lora_B = nn.Parameter(torch.empty(self.out_features, rank, device=device))

        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        original_output = F.linear(x, self.original_weight, self.original_bias)  # type:ignore

        lora_A_output = F.linear(x, self.lora_A)
        lora_B_output = F.linear(lora_A_output, self.lora_B)
        delta_output = lora_B_output * self.scaling
        return original_output + delta_output


class DoRA(nn.Module):
    def __init__(self, original_layer: nn.Linear, rank: int = 8, alpha: int = 8):
        super(DoRA, self).__init__()
        self.register_buffer(
            'original_weight',
            original_layer.weight.data,
            persistent=True
        )
        self.in_features = original_layer.in_features
        self.out_features = original_layer.out_features
        self.bias = original_layer.bias
        self.scaling = alpha / rank

        self.lora_A = nn.Parameter(torch.empty(rank, self.in_features))
        self.lora_B = nn.Parameter(torch.empty(self.out_features, rank))

        self.m = nn.Parameter(
            torch.linalg.norm(self.original_weight, dim=1, keepdim=True)
        )

        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        delta_W = self.lora_B @ self.lora_A
        delta_W = delta_W * self.scaling

        # 2. Compute the Adapted Directional Weight (W_dir)
        # W_dir = W_0 + Delta W
        W_dir = self.original_weight + delta_W  # type: ignore

        # 3. Compute the Current Magnitude (Current_m)
        # Current_m = ||W_dir||_2 for each row/output feature
        # (This is calculated on the fly as a vector of size [out_features, 1])
        W_dir_norm = torch.linalg.norm(W_dir, dim=1, keepdim=True)

        # 4. Compute the Final DoRA Weight (W_DoRA)
        # W_DoRA = m * (W_dir / Current_m)
        # This replaces the magnitude of W_dir with the trainable magnitude 'm'
        W_DoRA = self.m * (W_dir / W_dir_norm)

        # 5. Perform the linear transformation
        return F.linear(x, W_DoRA, self.bias)
