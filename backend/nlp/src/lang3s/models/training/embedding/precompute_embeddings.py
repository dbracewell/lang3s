import os
from typing import List

import numpy as np
import torch
from datasets import Dataset
from pydantic.main import BaseModel
from sentence_transformers import SentenceTransformer

from lang3s.models import Embedder
from .multilingual_dataset_loader import DataConfig, multilingual_text_stream

embedder = Embedder()


class PrecomputeConfig(BaseModel):
    out_dir: str = "data/distill_multilingual_mpnet_shards"
    teacher_model_name: str = "sentence-transformers/all-mpnet-base-v2"
    data_cfg: DataConfig = DataConfig()
    batch_size: int = 512  # for teacher.encode
    shard_size: int = 50_000
    seed: int = 1234


def precompute_teacher_embeddings_sharded(cfg: PrecomputeConfig):
    os.makedirs(cfg.out_dir, exist_ok=True)

    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    print(f"[precompute] Using device: {device}")

    teacher = SentenceTransformer(cfg.teacher_model_name, device=device)
    embedder.device = device

    stream = multilingual_text_stream(cfg.data_cfg)

    shard_texts: List[str] = []
    shard_idx = 0
    total_seen = 0

    for t in stream:
        shard_texts.append(t)
        total_seen += 1

        if len(shard_texts) >= cfg.shard_size:
            _encode_and_save_shard(
                shard_texts, shard_idx, teacher, cfg, device
            )
            shard_texts = []
            shard_idx += 1

    # last partial shard
    if shard_texts:
        _encode_and_save_shard(
            shard_texts, shard_idx, teacher, cfg, device
        )

    print(f"[precompute] Done. Total samples encoded: {total_seen}")


def _encode_and_save_shard(
    texts: List[str],
    shard_idx: int,
    teacher: SentenceTransformer,
    cfg: PrecomputeConfig,
    device: str,
):
    print(f"[precompute] Encoding shard {shard_idx} with {len(texts)} texts")

    # Optional: dedupe within shard
    seen = set()
    deduped_texts = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            deduped_texts.append(t)
    texts = deduped_texts

    emb = teacher.encode(
        texts,
        batch_size=cfg.batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    result = embedder(texts, is_split_into_words=False)

    ds = Dataset.from_dict({
        "text": texts,
        "teacher_emb": [e.astype(np.float32).tolist() for e in emb],  # type:ignore
        "student_emb": [e.astype(np.float32).tolist() for e in result.sentence_embeddings],
    })

    shard_path = os.path.join(cfg.out_dir, f"shard_{shard_idx:05d}")
    ds.save_to_disk(shard_path)
    print(f"[precompute] Saved shard {shard_idx} to {shard_path}")


if __name__ == "__main__":
    precompute_teacher_embeddings_sharded(PrecomputeConfig())
