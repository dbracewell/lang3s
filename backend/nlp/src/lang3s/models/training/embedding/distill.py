import os
import random
from typing import Any, Dict, List

import numpy as np
import torch
import torch.nn.functional as F
from datasets import load_from_disk
from huggingface_hub.utils.tqdm import tqdm
from pydantic.main import BaseModel
from torch.utils.data.dataloader import DataLoader

from lang3s.models import Embedder
from lang3s.models.layers.projection import SemanticProjectionHead


class TrainConfig(BaseModel):
    shards_dir: str = "data/distill_multilingual_mpnet_shards"
    output_path: str = "semantic_head_distilled_mpnet_multilingual.pt"
    batch_size: int = 64
    epochs: int = 1
    lr: float = 5e-5
    lambda_span: float = 1.0
    seed: int = 1234


def collate_with_teacher(batch: List[Dict[str, Any]]):
    texts = [b["text"] for b in batch]
    teacher_emb = torch.tensor([b["teacher_emb"] for b in batch], dtype=torch.float32)
    return texts, teacher_emb


def sample_spans_from_word_embeddings(
    word_embeddings: List,  # List[np.ndarray] or List[Tensor], per sentence
    device: str,
    max_span_len: int = 6,
) -> torch.Tensor:
    """
    For each sentence's word embeddings, sample one random span
    and average-pool its token vectors.

    Returns: span_embs: [batch_size, hidden_dim]
    """
    span_vecs = []
    for we in word_embeddings:
        we_t = torch.as_tensor(we, dtype=torch.float32, device=device)
        if we_t.ndim == 1:
            we_t = we_t.unsqueeze(0)
        num_tokens = we_t.size(0)

        if num_tokens == 0:
            span_vecs.append(torch.zeros(we_t.size(1), device=device))
            continue

        if num_tokens == 1:
            span_vecs.append(we_t[0])
            continue

        span_len = random.randint(1, min(max_span_len, num_tokens))
        start = random.randint(0, num_tokens - span_len)
        end = start + span_len
        span_vecs.append(we_t[start:end].mean(dim=0))

    return torch.stack(span_vecs, dim=0)


# ============================================================
# Teacher-similarity InfoNCE-like KL loss
# ============================================================
def teacher_similarity_info_nce_loss(
    student_emb: torch.Tensor,  # [B, D]
    teacher_emb: torch.Tensor,  # [B, D]
    t_temperature: float = 0.05,
    s_temperature: float = 0.05,
) -> torch.Tensor:
    """
    Distill teacher similarity structure into student using a KL-divergence
    between teacher and student similarity distributions.

    1) L2-normalize teacher & student
    2) Compute similarity matrices (cosine)
    3) Mask diagonal (no self-contrast)
    4) teacher_probs = softmax(teacher_sim / t_temp)
       student_log_probs = log_softmax(student_sim / s_temp)
    5) KLDiv(student_log_probs || teacher_probs)
    """
    B, D = student_emb.size()
    assert teacher_emb.size(0) == B

    teacher_norm = F.normalize(teacher_emb, p=2, dim=-1)
    student_norm = F.normalize(student_emb, p=2, dim=-1)

    teacher_sim = teacher_norm @ teacher_norm.t()  # [B,B]
    student_sim = student_norm @ student_norm.t()  # [B,B]

    mask = torch.eye(B, device=student_emb.device, dtype=torch.bool)
    teacher_sim = teacher_sim.masked_fill(mask, float("-inf"))
    student_sim = student_sim.masked_fill(mask, float("-inf"))

    teacher_logits = teacher_sim / t_temperature
    student_logits = student_sim / s_temperature

    teacher_probs = F.softmax(teacher_logits, dim=-1)
    log_student_probs = F.log_softmax(student_logits, dim=-1)

    loss = F.kl_div(log_student_probs, teacher_probs, reduction="batchmean")
    return loss


def train_distillation_sharded(cfg: TrainConfig):
    torch.manual_seed(cfg.seed)
    random.seed(cfg.seed)

    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"[train] Using device: {device}")

    # Find shard dirs
    shard_dirs = [
        os.path.join(cfg.shards_dir, d)
        for d in sorted(os.listdir(cfg.shards_dir))
        if d.startswith("shard_")
    ]
    if not shard_dirs:
        raise RuntimeError(f"No shards found in {cfg.shards_dir}")

    # Peek at first shard to get teacher_dim
    first_ds = load_from_disk(shard_dirs[0])
    teacher_dim = len(first_ds[0]["teacher_emb"])

    embedder = Embedder()
    embedder.device = device
    input_dim = embedder.dimensions

    head = SemanticProjectionHead(input_dim=input_dim, output_dim=teacher_dim)
    head.to(device)

    optimizer = torch.optim.AdamW(head.parameters(), lr=cfg.lr)
    max_grad_norm = 1.0

    global_step = 0

    for epoch in range(cfg.epochs):
        print(f"\n===== Epoch {epoch + 1}/{cfg.epochs} =====")

        total_loss = 0.0
        total_batches = 0

        for shard_path in shard_dirs:
            print(f"[train] Loading shard: {shard_path}")
            ds = load_from_disk(shard_path)
            loader = DataLoader(
                ds,
                batch_size=cfg.batch_size,
                shuffle=True,
                num_workers=2,
                collate_fn=collate_with_teacher,
            )

            head.train()
            for texts, teacher_sent_emb in tqdm(loader, desc=f"Shard {os.path.basename(shard_path)}"):
                teacher_sent_emb = teacher_sent_emb.to(device)

                # student sentence + span embeddings
                result = embedder(texts, is_split_into_words=False)
                student_sent_emb = torch.tensor(
                    np.array(result.sentence_embeddings),
                    dtype=torch.float32,
                    device=device,
                )
                proj_sent = head(student_sent_emb)

                student_span_hidden = sample_spans_from_word_embeddings(
                    result.word_embeddings, device=device
                )
                proj_span = head(student_span_hidden)

                loss_sent = teacher_similarity_info_nce_loss(
                    student_emb=proj_sent,
                    teacher_emb=teacher_sent_emb,
                    t_temperature=0.05,
                    s_temperature=0.05,
                )
                loss_span = teacher_similarity_info_nce_loss(
                    student_emb=proj_span,
                    teacher_emb=teacher_sent_emb,
                    t_temperature=0.05,
                    s_temperature=0.05,
                )

                loss = loss_sent + cfg.lambda_span * loss_span

                optimizer.zero_grad()
                loss.backward()
                if max_grad_norm is not None:
                    torch.nn.utils.clip_grad_norm_(head.parameters(), max_grad_norm)
                optimizer.step()

                global_step += 1
                total_batches += 1
                total_loss += loss.item()

        avg_loss = total_loss / max(1, total_batches)
        print(f"[train] Epoch {epoch + 1} avg_loss = {avg_loss:.4f}")

        ckpt_path = f"{os.path.splitext(cfg.output_path)[0]}.epoch{epoch + 1}.pt"
        torch.save(head.state_dict(), ckpt_path)
        print(f"[train] Saved checkpoint: {ckpt_path}")

    torch.save(head.state_dict(), cfg.output_path)
    print(f"[train] Final projection head saved to: {cfg.output_path}")


def train_distillation_v2(cfg: TrainConfig):
    torch.manual_seed(cfg.seed)
    random.seed(cfg.seed)

    # Device
    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    print(f"[train-v2] Using device: {device}")

    # Load shard paths
    shard_dirs = [
        os.path.join(cfg.shards_dir, d)
        for d in sorted(os.listdir(cfg.shards_dir))
        if d.startswith("shard_")
    ]
    if not shard_dirs:
        raise RuntimeError("No shards found!")

    # Detect teacher dimension from the first shard
    first_ds = load_from_disk(shard_dirs[0])
    teacher_dim = len(first_ds[0]["teacher_emb"])

    embedder = Embedder()
    embedder.device = device
    student_dim = embedder.dimensions

    print(f"Student input dim: {student_dim}, Teacher dim: {teacher_dim}")

    # Projection head from student_dim → teacher_dim
    head = SemanticProjectionHead(
        input_dim=student_dim,
        output_dim=teacher_dim
    )
    head.to(device)

    optimizer = torch.optim.AdamW(head.parameters(), lr=cfg.lr)
    max_grad_norm = 1.0

    lambda_mse = 1.0  # Regression weight
    t_temp = 0.03  # teacher logits temp
    s_temp = 0.05  # student logits temp

    global_step = 0

    for epoch in range(cfg.epochs):
        print(f"\n===== Epoch {epoch + 1}/{cfg.epochs} =====")

        total_loss = 0.0
        total_batches = 0

        for shard_id, shard_path in enumerate(shard_dirs):
            print(f"[train-v2] Loading shard: {shard_path}")
            ds = load_from_disk(shard_path)

            loader = DataLoader(
                ds,
                batch_size=cfg.batch_size,
                shuffle=True,
                num_workers=2,
                collate_fn=collate_with_teacher,
            )

            for texts, teacher_emb in tqdm(loader, desc=f"Shard {os.path.basename(shard_path)}"):
                teacher_emb = teacher_emb.to(device)

                # Student embeddings
                res = embedder(texts, is_split_into_words=False)
                student_sent = torch.tensor(
                    np.array(res.sentence_embeddings),
                    dtype=torch.float32,
                    device=device,
                )

                proj_student = head(student_sent)

                # 1) Alignment loss (InfoNCE KL)
                loss_sent = teacher_similarity_info_nce_loss(
                    student_emb=proj_student,
                    teacher_emb=teacher_emb,
                    t_temperature=t_temp,
                    s_temperature=s_temp
                )

                # 2) Direct embedding regression
                loss_mse = F.mse_loss(proj_student, teacher_emb)

                loss = loss_sent + lambda_mse * loss_mse

                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), max_grad_norm)
                optimizer.step()

                total_loss += loss.item()
                total_batches += 1
                global_step += 1

            shard_ckpt = f"{cfg.output_path}.epoch{epoch + 1}.shard{shard_id}.pt"
            torch.save(head.state_dict(), shard_ckpt)
            print(f"[train-v2] Saved shard checkpoint: {shard_ckpt}")

        avg_loss = total_loss / total_batches
        print(f"[train-v2] Epoch {epoch + 1} avg loss: {avg_loss:.4f}")

        # Save checkpoint
        ckpt = f"{cfg.output_path}.epoch{epoch + 1}.pt"
        torch.save(head.state_dict(), ckpt)
        print(f"[train-v2] Saved checkpoint: {ckpt}")

    # Final save
    torch.save(head.state_dict(), cfg.output_path)
    print(f"[train-v2] Final head saved to: {cfg.output_path}")


if __name__ == "__main__":
    # train_distillation_sharded(TrainConfig())
    train_distillation_v2(cfg=TrainConfig(batch_size=512))
