from typing import Tuple

import torch
import torch.distributions as dist
from torch import nn


class Mixup(nn.Module):

    def __init__(self, alpha: float = 0.2, loss_fn: nn.Module = nn.CrossEntropyLoss()):
        super(Mixup, self).__init__()
        self.alpha = alpha
        self.loss_fn = loss_fn
        if self.alpha > 0.0:
            self.beta_dist = dist.Beta(self.alpha, self.alpha)

    def augment(self, x: torch.Tensor, y: torch.Tensor) -> Tuple[
        torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.alpha > 0:
            lam = self.beta_dist.sample().to(x.device)
        else:
            lam = torch.tensor(1.0).to(x.device)

        batch_size = x.size(0)
        index = torch.randperm(batch_size).to(x.device)
        mixed_x: torch.Tensor = lam * x + (1 - lam) * x[index, ...]
        y_a, y_b = y, y[index]
        return mixed_x, y_a, y_b, lam

    def forward(self, pred, y_a, y_b, lam):
        return lam * self.loss_fn(pred, y_a) + (1 - lam) * self.loss_fn(pred, y_b)
