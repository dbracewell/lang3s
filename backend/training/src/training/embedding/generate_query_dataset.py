import pickle

import numpy as np
import torch
from datasets import load_dataset
from torch.utils.data import Dataset
from tqdm import tqdm

from lang3s.models.embedder import Embedder


# --- 1. DATASET CLASS (Fixed Keys) ---
class QueryDistillationDataset(Dataset):
    def __init__(self, data_path):
        print(f"Loading precomputed data from {data_path}...")
        with open(data_path, "rb") as f:
            data = pickle.load(f)

        # Load as Float Tensors (CPU) to prevent overhead during training
        self.anchors = torch.from_numpy(data["anchors"]).float()
        self.positive_embeddings = torch.from_numpy(data["positive_embeddings"]).float()
        self.negative_embeddings = torch.from_numpy(data["negative_embeddings"]).float()

        print(f"Loaded {len(self.anchors)} training samples.")

    def __len__(self):
        return len(self.anchors)

    def __getitem__(self, idx):
        # FIX: Keys now match your training loop
        return {
            "query": self.anchors[idx],
            "target_vec": self.positive_embeddings[idx],
            "negative_vec": self.negative_embeddings[idx],
        }


# --- 2. GENERATOR FUNCTION ---
def prepare_distillation_data(raw_records, output_path, batch_size):
    teacher_model = Embedder()
    print("Extracting unique sentences from raw records...")

    anchors = []
    positive = []
    negative = []

    for record in tqdm(raw_records, desc="Filtering"):
        anc = record.get("anchor")
        pos = record.get("positive")
        neg = record.get("negative")

        # FIX: Handle potential Lists in MS MARCO
        if isinstance(pos, list):
            pos = pos[0] if len(pos) > 0 else ""
        if isinstance(neg, list):
            neg = neg[0] if len(neg) > 0 else ""

        if anc and pos and neg and is_clean(anc) and is_clean(pos) and is_clean(neg):
            anchors.append(anc)
            positive.append(pos)
            negative.append(neg)

    print(f"Found {len(anchors)} clean triplets.")

    # --- Precompute Embeddings ---
    print("Computing Embeddings...")

    # Helpers for batch processing
    def embed_batch(texts):
        # Embedder returns numpy; convert to tensor
        with torch.no_grad():
            res = teacher_model(texts).sentence_embeddings
            return torch.tensor(np.stack(res))

    positive_embeddings = []
    negative_embeddings = []

    for i in tqdm(range(0, len(anchors), batch_size)):
        positive_embeddings.append(embed_batch(positive[i : i + batch_size]))
        negative_embeddings.append(embed_batch(negative[i : i + batch_size]))

    # Save
    if len(anchors) > 0:
        payload = {
            "anchors": anchors,
            "positive_embeddings": torch.cat(positive_embeddings, dim=0).numpy(),
            "negative_embeddings": torch.cat(negative_embeddings, dim=0).numpy(),
        }

        with open(output_path, "wb") as f:
            pickle.dump(payload, f)

    print(f"Saved processed dataset to {output_path}")


def is_clean(text):
    if not isinstance(text, str):
        return False
    # Increased max len to 1200 because MS MARCO passages can be long
    if len(text) < 5 or len(text) > 1200:
        return False
    return True


if __name__ == "__main__":
    OUTPUT_FILE = "query_training_data.pkl"

    print("Loading MS MARCO (Search Data)...")
    try:
        # Removed "triplet" config name to use default (safer)
        ds_marco = load_dataset(
            "sentence-transformers/msmarco-msmarco-MiniLM-L6-v3",
            "triplet",
            split="train[:500000]",
        )

        raw_records = []
        for row in tqdm(ds_marco, desc="Loading"):
            raw_records.append(
                {
                    "anchor": row["query"],
                    "positive": row["positive"],
                    "negative": row["negative"],
                }
            )

        print(f"Added {len(raw_records)} raw samples.")

        prepare_distillation_data(
            raw_records=raw_records,
            output_path=OUTPUT_FILE,
            batch_size=128,
        )
        print("\n✅ Data Preparation Complete.")

    except Exception as e:
        print(f"Error: {e}")
