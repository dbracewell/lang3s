import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================
# Projection head: XLM-R hidden -> semantic space
# ============================================================
class SemanticProjectionHead(nn.Module):
    def __init__(self, input_dim: int, output_dim: int = 768, hidden_dim: int = 1024):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [batch, input_dim]
        x = self.net(x)
        return F.normalize(x, p=2, dim=-1)
