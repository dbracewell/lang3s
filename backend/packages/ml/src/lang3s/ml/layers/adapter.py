import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class LoRAActivationAdapter(nn.Module):
    def __init__(self,
                 hidden_size: int,
                 rank: int = 8,
                 dropout: float = 0.1,
                 alpha: int = 8):
        super(LoRAActivationAdapter, self).__init__()
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


class DoRAActivationAdapter(nn.Module):
    """
    DoRA-style low-rank adapter for activation space (not tied to any pretrained W0).

    Computes:
        H' = magnitude * normalize(H + ΔH)

    where:
        ΔH = up(down(H))
        normalize(x) = x / (||x|| + eps)

    This is the correct DoRA-like adaptation when NOT modifying a pretrained weight.
    """

    def __init__(
        self,
        hidden_size: int,
        rank: int = 8,
        dropout: float = 0.1,
        eps: float = 1e-6,
    ):
        super().__init__()

        self.rank = rank
        self.eps = eps

        # Low-rank adapter
        self.down = nn.Linear(hidden_size, rank, bias=False)
        self.up = nn.Linear(rank, hidden_size, bias=False)
        self.dropout = nn.Dropout(dropout)

        # Scaling (LoRA-style)
        self.scaling = 1.0 / rank

        # DoRA magnitude (learnable)
        self.magnitude = nn.Parameter(torch.ones(1))

        # Initialization
        nn.init.kaiming_uniform_(self.down.weight, a=math.sqrt(5))
        nn.init.zeros_(self.up.weight)

    def forward(self, x):
        # Compute ΔH
        delta = self.up(self.dropout(self.down(x)))
        delta = self.scaling * delta

        # DoRA direction update
        direction = x + delta

        # Normalize direction per feature vector
        direction_norm = direction.norm(dim=-1, keepdim=True) + self.eps
        direction_normalized = direction / direction_norm

        # Apply learned magnitude
        out = self.magnitude * direction_normalized

        return out


class DoRAActivationAdapterForSequence(nn.Module):
    """
    DoRA-style activation adapter for sequence labeling (NER, chunking, POS, etc.)
    with PER-FEATURE magnitude instead of scalar.

    Input:  (batch, seq_len, hidden_size)
    Output: (batch, seq_len, hidden_size)

    Computes for each token:
        Δh = Up( Dropout( Down(h) ) )
        direction = h + Δh
        direction_norm = ||direction||_2 over hidden dim
        normalized_direction = direction / (direction_norm + eps)
        h' = magnitude_vector * normalized_direction

    magnitude_vector: learnable parameter of shape (hidden_size,)
    """

    def __init__(
        self,
        hidden_size: int,
        rank: int = 8,
        dropout: float = 0.1,
        eps: float = 1e-6,
    ):
        super().__init__()

        self.rank = rank
        self.hidden_size = hidden_size
        self.eps = eps

        # Low-rank decomposition
        self.down = nn.Linear(hidden_size, rank, bias=False)
        self.up = nn.Linear(rank, hidden_size, bias=False)
        self.dropout = nn.Dropout(dropout)

        # Rank compensation (optional but helpful)
        self.scaling = 1.0 / rank

        # ⭐ Per-feature magnitude vector
        # Shape: (hidden_size,)
        self.magnitude = nn.Parameter(torch.ones(hidden_size))

        # Initialization
        nn.init.kaiming_uniform_(self.down.weight, a=math.sqrt(5))
        nn.init.zeros_(self.up.weight)

    def forward(self, x):
        """
        x: (batch, seq_len, hidden_size)
        """

        # Low-rank ΔH
        delta = self.up(self.dropout(self.down(x)))
        delta = self.scaling * delta

        # Direction update
        direction = x + delta

        # Normalize per token along hidden dimension
        # direction_norm: (batch, seq_len, 1)
        direction_norm = direction.norm(dim=-1, keepdim=True) + self.eps
        direction_normalized = direction / direction_norm

        # magnitude shape: (hidden_size,) → broadcast to (batch, seq_len, hidden_size)
        out = direction_normalized * self.magnitude

        return out


class ParallelLoRAAndDoRAActivationAdapterForSequence(nn.Module):
    """
    Parallel LoRA + DoRA activation adapter for sequence labeling.

    Input:  (batch, seq_len, hidden_size)
    Output: (batch, seq_len, hidden_size)

    For each token h_t:

        # LoRA branch (directional low-rank update)
        Δh_lora = scale_lora * Up_lora( Dropout( Down_lora(h_t) ) )

        # DoRA branch (normalized low-rank update with per-feature magnitude)
        Δh_dora_raw = Up_dora( Dropout( Down_dora(h_t) ) )
        direction   = h_t + Δh_dora_raw
        direction_n = direction / (||direction||_2 + eps)
        h_dora      = magnitude * direction_n      # per-feature magnitude
        Δh_dora     = h_dora - h_t                 # residual form

        # Gated combination
        [w_lora, w_dora] = softmax([gate_lora, gate_dora])
        h_t' = h_t + w_lora * Δh_lora + w_dora * Δh_dora

    Design goals:
      - Small-data friendly (normalization + gating + dropout)
      - Still works great on CoNLL-sized datasets
      - Plug-and-play on frozen transformer encoders.
    """

    def __init__(
        self,
        hidden_size: int,
        rank_lora: int = 8,
        rank_dora: int = 8,
        alpha_lora: int = 8,
        dropout: float = 0.1,
        eps: float = 1e-6,
        init_dora_weight: float = 0.7,
        init_lora_weight: float = 0.3,
    ):
        super().__init__()

        self.hidden_size = hidden_size
        self.rank_lora = rank_lora
        self.rank_dora = rank_dora
        self.eps = eps

        # ----- LoRA branch -----
        self.down_lora = nn.Linear(hidden_size, rank_lora, bias=False)
        self.up_lora = nn.Linear(rank_lora, hidden_size, bias=False)
        # Classic LoRA scaling (alpha / r)
        self.lora_scaling = alpha_lora / rank_lora

        # ----- DoRA branch -----
        self.down_dora = nn.Linear(hidden_size, rank_dora, bias=False)
        self.up_dora = nn.Linear(rank_dora, hidden_size, bias=False)
        # Optional mild rank compensation (1 / r) to keep init small
        self.dora_scaling = 1.0 / rank_dora

        # Per-feature magnitude vector (shape: [hidden_size])
        self.magnitude = nn.Parameter(torch.ones(hidden_size))

        self.dropout = nn.Dropout(dropout)

        # ----- Gating between LoRA and DoRA -----
        # We parametrize two scalars and softmax them to get stable weights.
        # Initialize to favor DoRA (more stable on small data), but not exclusively.
        self.gate_lora = nn.Parameter(
            torch.tensor(init_lora_weight, dtype=torch.float32)
        )
        self.gate_dora = nn.Parameter(
            torch.tensor(init_dora_weight, dtype=torch.float32)
        )

        # ----- Initialization -----
        # LoRA: Kaiming for down, zeros for up (LoRA standard)
        nn.init.kaiming_uniform_(self.down_lora.weight, a=math.sqrt(5))
        nn.init.zeros_(self.up_lora.weight)

        # DoRA: same style
        nn.init.kaiming_uniform_(self.down_dora.weight, a=math.sqrt(5))
        nn.init.zeros_(self.up_dora.weight)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch, seq_len, hidden_size)
        """
        # ----- LoRA branch -----
        # Low-rank ΔH_lora
        delta_lora = self.up_lora(self.dropout(self.down_lora(x)))
        delta_lora = self.lora_scaling * delta_lora  # (b, s, h)

        # ----- DoRA branch -----
        # Raw low-rank update
        delta_dora_raw = self.up_dora(self.dropout(self.down_dora(x)))
        delta_dora_raw = self.dora_scaling * delta_dora_raw  # (b, s, h)

        # Direction update
        direction = x + delta_dora_raw  # (b, s, h)

        # Normalize along hidden dimension, per token
        direction_norm = direction.norm(dim=-1, keepdim=True) + self.eps  # (b, s, 1)
        direction_normalized = direction / direction_norm  # (b, s, h)

        # Per-feature magnitude (broadcast over batch & seq_len)
        h_dora = direction_normalized * self.magnitude  # (b, s, h)

        # Residual form for DoRA branch
        delta_dora = h_dora - x  # (b, s, h)

        # ----- Gated combination -----
        # Softmax over two scalar gates → [w_lora, w_dora]
        gates = torch.stack([self.gate_lora, self.gate_dora], dim=0)  # (2,)
        weights = torch.softmax(gates, dim=0)
        w_lora, w_dora = weights[0], weights[1]

        # Final residual combination
        out = x + w_lora * delta_lora + w_dora * delta_dora  # (b, s, h)

        return out


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
            "original_weight",
            (
                original_layer.weight.data.to(device)
                if device
                else original_layer.weight.data
            ),
            persistent=True,
        )

        if self.has_bias:
            self.register_buffer(
                "original_bias",
                (
                    original_layer.bias.data.to(device)
                    if device
                    else original_layer.bias.data
                ),
                persistent=True,
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
