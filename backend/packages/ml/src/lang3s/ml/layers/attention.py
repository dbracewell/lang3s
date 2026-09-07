import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class FastLocalWindowAttention(nn.Module):
    """
    FAST sliding-window attention using torch.roll().
    No conv, no unfold, no indexing → works on MPS, CUDA, CPU.
    """

    def __init__(self, hidden_size, num_heads=2, window_radius=3, dropout=0.1):
        super().__init__()
        assert hidden_size % num_heads == 0

        self.hidden = hidden_size
        self.heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.r = window_radius
        self.w = 2 * window_radius + 1

        self.q_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.k_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.v_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.out_proj = nn.Linear(hidden_size, hidden_size, bias=False)

        self.dropout = nn.Dropout(dropout)

    def extract_roll_windows(self, x):
        """
        x: (B, heads, T, D)
        Return windows: (B, heads, T, W, D)
        """
        B, H, T, D = x.shape

        windows = []
        for offset in range(-self.r, self.r + 1):
            rolled = torch.roll(x, shifts=offset, dims=2)
            # Fix boundary using padding mask later
            windows.append(rolled)

        # (W, B, heads, T, D) → (B, heads, T, W, D)
        return torch.stack(windows, dim=3)

    def forward(self, x, mask=None):
        """
        x: (B, T, H)
        mask: (B, T) boolean
        """
        B, T, H = x.size()

        # Project
        q = self.q_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        # shapes: (B, heads, T, D)

        # Extract windows via roll
        k_w = self.extract_roll_windows(k)  # (B, heads, T, W, D)
        v_w = self.extract_roll_windows(v)

        # Compute attention logits
        q_exp = q.unsqueeze(3)  # (B, heads, T, 1, D)
        att = (q_exp * k_w).sum(-1) / math.sqrt(self.head_dim)  # (B, heads, T, W)

        # Mask invalid tokens + boundary roll artifacts
        if mask is not None:
            # mask: (B, T) → (B, 1, T, 1)
            m_exp = mask.unsqueeze(1).unsqueeze(3)
            # Window mask (roll-shifted mask)
            mask_w = (
                self.extract_roll_windows(m_exp.float()).squeeze(-1).bool()
            )  # (B, heads?, T, W)

            # Because m_exp had shape (B,1,T,1), extract produces shape (B,1,T,W)
            mask_w = mask_w.squeeze(1).unsqueeze(1)  # (B,1,T,W) → (B,1,T,W)
            att = att.masked_fill(~mask_w, float("-inf"))

            # Fix rows that are fully invalid
            all_inf = torch.isneginf(att).all(-1, keepdim=True)
            att = att.masked_fill(all_inf, 0)

        # Softmax
        att = torch.softmax(att, dim=-1)
        att = self.dropout(att)

        # Weighted sum: (B, heads, T, D)
        out = (att.unsqueeze(-1) * v_w).sum(3)

        # Merge heads
        out = out.transpose(1, 2).reshape(B, T, H)
        return self.out_proj(out)


class LocalWindowAttention(nn.Module):
    """
    Sliding window attention that avoids unfold() to guarantee
    correct dimension alignment on CUDA and MPS.
    """

    def __init__(self, hidden_size, num_heads=2, window_radius=3, dropout=0.1):
        super().__init__()
        assert hidden_size % num_heads == 0

        self.hidden = hidden_size
        self.heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.r = window_radius
        self.w = 2 * window_radius + 1

        self.q_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.k_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.v_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.out_proj = nn.Linear(hidden_size, hidden_size, bias=False)

        self.dropout = nn.Dropout(dropout)

    def forward(self, x, mask=None):
        """
        x: (B, T, H)
        mask: (B, T)
        """
        B, T, H = x.size()

        # Project
        q = self.q_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        # shapes: (B, heads, T, head_dim)

        # Pad K/V for window extraction
        k_pad = F.pad(k, (0, 0, self.r, self.r))  # pad T dimension
        v_pad = F.pad(v, (0, 0, self.r, self.r))

        # Build window indices dynamically (NO UNFOLD)
        idx = torch.arange(T, device=x.device).unsqueeze(1)  # (T,1)
        offsets = torch.arange(-self.r, self.r + 1, device=x.device)  # (w,)
        window_indices = idx + offsets  # (T, w)
        window_indices = window_indices.clamp(0, T + 2 * self.r - 1)

        # Gather sliding windows
        # k_win: (B, heads, T, w, head_dim)
        k_win = k_pad[:, :, window_indices, :]
        v_win = v_pad[:, :, window_indices, :]

        # Compute attention score
        q_exp = q.unsqueeze(3)  # (B, heads, T, 1, head_dim)

        att = (q_exp * k_win).sum(-1) / math.sqrt(self.head_dim)  # (B, heads, T, w)

        # Mask (if provided)
        if mask is not None:
            # pad mask like we padded k
            mask_pad = F.pad(mask.unsqueeze(1).float(), (self.r, self.r))
            mask_win = mask_pad[:, :, window_indices].bool()  # (B, 1, T, w)
            att = att.masked_fill(~mask_win, float("-inf"))
            # Fix all-inf rows
            all_inf = torch.isneginf(att).all(-1, keepdim=True)
            att = att.masked_fill(all_inf, 0)

        # Softmax over w
        att = torch.softmax(att, dim=-1)
        att = self.dropout(att)

        # Weighted sum of v_win
        out = (att.unsqueeze(-1) * v_win).sum(dim=3)  # (B, heads, T, head_dim)

        # Combine heads
        out = out.transpose(1, 2).reshape(B, T, H)
        return self.out_proj(out)
