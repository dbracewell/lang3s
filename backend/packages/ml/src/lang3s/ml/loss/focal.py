import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Focal Loss implementation supporting Multi-class, Binary, and Multi-label tasks.
    """

    def __init__(self, gamma=2.0, alpha=0.25, loss_type="multiclass", reduction="mean"):
        """
        Args:
            gamma (float): Focusing parameter. Higher gamma reduces loss for easy examples.
            alpha (float or torch.Tensor): Weighting factor for the positive class (or per-class).
            loss_type (str): 'multiclass', 'binary', or 'multilabel'.
            reduction (str): 'mean' or 'sum'.
        """
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction
        self.loss_type = loss_type.lower()

        if self.loss_type not in ["multiclass", "binary", "multilabel"]:
            raise ValueError(
                "loss_type must be 'multiclass', 'binary', or 'multilabel'"
            )

        if isinstance(alpha, (int, float)):
            self.alpha = torch.tensor([alpha], dtype=torch.float32)
        elif isinstance(alpha, torch.Tensor):
            self.alpha = alpha.float()
        else:
            self.alpha = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        if self.loss_type == "multiclass":
            ce_loss = F.cross_entropy(logits, targets, reduction="none")
            pt = torch.exp(-ce_loss)
            if self.alpha is not None:
                alpha_t = self.alpha.gather(0, targets.data.view(-1)).to(logits.device)
            else:
                alpha_t = torch.ones_like(pt)

        elif self.loss_type in ["binary", "multilabel"]:
            ce_loss = F.binary_cross_entropy_with_logits(
                logits, targets.float(), reduction="none"
            )
            p = torch.sigmoid(logits)
            pt = p * targets + (1 - p) * (1 - targets)
            if self.alpha is not None:
                alpha_device = self.alpha.to(logits.device)
                if (
                    self.loss_type == "multilabel"
                    and alpha_device.dim() == 1
                    and alpha_device.size(0) == logits.size(1)
                ):
                    alpha_t = alpha_device.unsqueeze(0).expand_as(targets) * targets + (
                        1 - alpha_device.unsqueeze(0).expand_as(targets)
                    ) * (1 - targets)
                else:
                    alpha_t = alpha_device * targets + (1 - alpha_device) * (
                        1 - targets
                    )
            else:
                alpha_t = torch.ones_like(pt)

        else:
            raise NotImplementedError

        # Focusing term: (1 - p_t)^gamma
        modulating_factor = (1.0 - pt) ** self.gamma

        # Apply the full Focal Loss formula
        loss = alpha_t * modulating_factor * ce_loss

        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        else:
            return loss


class MaskedFocalLoss(nn.Module):
    """
    Focal Loss (multi-class, binary, multi-label) with ignore_index support.
    """

    def __init__(
        self,
        gamma=2.0,
        alpha=0.25,
        loss_type="multiclass",
        reduction="mean",
        ignore_index=-100,
    ):
        """
        Args:
            gamma: focusing parameter
            alpha: per-class or scalar weight
            loss_type: 'multiclass', 'binary', 'multilabel'
            reduction: 'mean' or 'sum' or 'none'
            ignore_index: index to ignore from both CE and focal calculations
        """
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
        self.loss_type = loss_type.lower()
        self.ignore_index = ignore_index

        if isinstance(alpha, (int, float)):
            self.alpha = (
                None if alpha is None else torch.tensor([alpha], dtype=torch.float32)
            )
        else:
            self.alpha = alpha.float() if isinstance(alpha, torch.Tensor) else None

        if self.loss_type not in ["multiclass", "binary", "multilabel"]:
            raise ValueError(
                "loss_type must be 'multiclass', 'binary', or 'multilabel'"
            )

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        logits: (N, C) for multiclass, or (N, C) for multilabel/binary
        targets: same spatial shape, long for multiclass, float/binary for multilabel/binary
        """

        # ----------------------------------------------------------------------
        # 0. Mask ignored indices BEFORE any focal-loss math
        # ----------------------------------------------------------------------
        if self.ignore_index is not None and self.loss_type == "multiclass":
            # mask: True for positions to keep
            keep = (targets != self.ignore_index).view(-1)
            if keep.sum() == 0:
                return torch.tensor(0.0, device=logits.device)
            logits = logits.view(-1, logits.size(-1))[keep]
            targets = targets.view(-1)[keep]

        elif self.ignore_index is not None and self.loss_type in [
            "binary",
            "multilabel",
        ]:
            # For multilabel, ignore_index means: remove rows where ALL positions are ignore_index
            if self.ignore_index == -100:
                # mask positions where target != ignore_index
                keep = targets != self.ignore_index
                if keep.sum() == 0:
                    return torch.tensor(0.0, device=logits.device)
                logits = logits[keep]
                targets = targets[keep]
            else:
                pass  # optional custom logic

        # ----------------------------------------------------------------------
        # 1. MULTICLASS CASE
        # ----------------------------------------------------------------------
        if self.loss_type == "multiclass":
            # Cross entropy per token
            ce_loss = F.cross_entropy(logits, targets, reduction="none")

            # p_t
            pt = torch.exp(-ce_loss)

            # per-class alpha
            if self.alpha is not None:
                alpha_t = self.alpha.to(logits.device).gather(0, targets)
            else:
                alpha_t = torch.ones_like(pt)

        # ----------------------------------------------------------------------
        # 2. BINARY / MULTILABEL CASE
        # ----------------------------------------------------------------------
        elif self.loss_type in ["binary", "multilabel"]:
            ce_loss = F.binary_cross_entropy_with_logits(
                logits, targets.float(), reduction="none"
            )

            # pt = p if target==1 else (1-p)
            p = torch.sigmoid(logits)
            pt = p * targets + (1 - p) * (1 - targets)

            # per-class alpha (optionally per-label)
            if self.alpha is not None:
                alpha = self.alpha.to(logits.device)
                if alpha.numel() == logits.size(-1):
                    alpha_t = alpha.unsqueeze(0).expand_as(targets)
                    alpha_t = alpha_t * targets + (1 - alpha_t) * (1 - targets)
                else:
                    alpha_t = alpha * targets + (1 - alpha) * (1 - targets)
            else:
                alpha_t = torch.ones_like(pt)

        else:
            raise NotImplementedError

        # ----------------------------------------------------------------------
        # 3. Focal Loss Formula
        # ----------------------------------------------------------------------
        modulating_factor = (1.0 - pt) ** self.gamma
        loss = alpha_t * modulating_factor * ce_loss

        # ----------------------------------------------------------------------
        # 4. Reduction
        # ----------------------------------------------------------------------
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        else:
            return loss
