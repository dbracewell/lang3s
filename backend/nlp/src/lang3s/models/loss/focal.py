import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Focal Loss implementation supporting Multi-class, Binary, and Multi-label tasks.
    """

    def __init__(self, gamma=2.0, alpha=0.25, loss_type='multiclass', reduction='mean'):
        """
        Args:
            gamma (float): Focusing parameter. Higher gamma reduces loss for easy examples.
            alpha (float or torch.Tensor): Weighting factor for the positive class (or per-class).
            loss_type (str): 'multiclass', 'binary', or 'multilabel'.
            reduction (str): 'mean' or 'sum'.
        """
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha  # Renamed 'weight' to 'alpha' for clarity in FL literature
        self.reduction = reduction
        self.loss_type = loss_type.lower()

        if self.loss_type not in ['multiclass', 'binary', 'multilabel']:
            raise ValueError("loss_type must be 'multiclass', 'binary', or 'multilabel'")

        if isinstance(alpha, (int, float)):
            self.alpha = torch.tensor([alpha], dtype=torch.float32)
        elif isinstance(alpha, torch.Tensor):
            self.alpha = alpha.float()
        else:
            self.alpha = None

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:

        if self.loss_type == 'multiclass':
            ce_loss = F.cross_entropy(logits, targets, reduction='none')
            pt = torch.exp(-ce_loss)
            if self.alpha is not None:
                alpha_t = self.alpha.gather(0, targets.data.view(-1)).to(logits.device)
            else:
                alpha_t = torch.ones_like(pt)

        elif self.loss_type in ['binary', 'multilabel']:
            ce_loss = F.binary_cross_entropy_with_logits(
                logits, targets.float(), reduction='none'
            )
            p = torch.sigmoid(logits)
            pt = p * targets + (1 - p) * (1 - targets)
            if self.alpha is not None:
                alpha_device = self.alpha.to(logits.device)
                if self.loss_type == 'multilabel' and alpha_device.dim() == 1 and alpha_device.size(0) == logits.size(
                    1):
                    alpha_t = alpha_device.unsqueeze(0).expand_as(targets) * targets + \
                              (1 - alpha_device.unsqueeze(0).expand_as(targets)) * (1 - targets)
                else:
                    alpha_t = alpha_device * targets + (1 - alpha_device) * (1 - targets)
            else:
                alpha_t = torch.ones_like(pt)

        else:
            raise NotImplementedError

        # Focusing term: (1 - p_t)^gamma
        modulating_factor = (1.0 - pt) ** self.gamma

        # Apply the full Focal Loss formula
        loss = alpha_t * modulating_factor * ce_loss

        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        else:
            return loss
