import torch.nn as nn


class SequenceMultiHeadSelfAttention(nn.Module):
    def __init__(self, hidden_size, num_heads=4, dropout=0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            batch_first=True,
            dropout=dropout,
        )
        self.ln = nn.LayerNorm(hidden_size)
        self.drop = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        key_padding_mask = None
        if mask is not None:
            key_padding_mask = ~mask.bool()

        attn_out, _ = self.attn(
            x, x, x,
            key_padding_mask=key_padding_mask,
        )

        return self.ln(x + self.drop(attn_out))

#
# class SelfAttentionPooling(nn.Module):
#     """
#     Self-attention pooling over word embeddings.
#
#     Input:
#         word_embs: Tensor [seq_len, hidden]
#
#     Output:
#         pooled: Tensor [hidden]
#     """
#
#     def __init__(self, hidden_size: int, dropout: float = 0.1):
#         super().__init__()
#
#         # Standard attention scoring: score_i = vᵀ tanh(Wx_i)
#         self.attention_w = nn.Linear(hidden_size, hidden_size)
#         self.attention_v = nn.Linear(hidden_size, 1, bias=False)
#
#         self.dropout = nn.Dropout(dropout)
#         self.hidden_size = hidden_size
#
#     def forward(self, word_embs: torch.Tensor) -> torch.Tensor:
#         """
#         word_embs: [seq_len, hidden]
#         Returns a pooled vector: [hidden]
#         """
#
#         if word_embs.ndim != 2:
#             raise ValueError(f"Expected [seq_len, hidden], got {word_embs.shape}")
#
#         # Compute attention scores
#         # h = tanh(Wx)
#         h = torch.tanh(self.attention_w(word_embs))  # [seq_len, hidden]
#
#         # score = vᵀ h
#         scores = self.attention_v(h).squeeze(-1)  # [seq_len]
#
#         # Attention weights
#         attn = torch.softmax(scores, dim=0)  # [seq_len]
#         attn = self.dropout(attn)  # regularize
#
#         # Weighted sum
#         pooled = torch.sum(word_embs * attn.unsqueeze(-1), dim=0)  # [hidden]
#
#         return pooled
#
#
# class MultiHeadSelfAttentionPooling(nn.Module):
#     """
#     Multi-head self-attention pooling.
#     Input shape: [seq_len, hidden]
#     Output shape: [hidden * num_heads] OR [hidden] with reduction.
#     """
#
#     def __init__(
#         self,
#         hidden_size: int,
#         num_heads: int = 4,
#         dropout: float = 0.1,
#         concat: bool = True,
#     ):
#         super().__init__()
#
#         self.heads = nn.ModuleList([
#             SelfAttentionPooling(hidden_size, dropout)
#             for _ in range(num_heads)
#         ])
#         self.concat = concat
#         self.hidden_size = hidden_size
#         self.num_heads = num_heads
#
#     def forward(self, word_embs: torch.Tensor) -> torch.Tensor:
#         pooled = [head(word_embs) for head in self.heads]
#
#         if self.concat:
#             # [hidden * num_heads]
#             return torch.cat(pooled, dim=-1)
#
#         # Alternatively: mean over heads → [hidden]
#         return torch.stack(pooled, dim=0).mean(dim=0)
