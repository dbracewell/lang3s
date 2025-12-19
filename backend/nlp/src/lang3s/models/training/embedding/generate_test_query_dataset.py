import pickle
import numpy as np
import torch
from tqdm import tqdm
from datasets import load_dataset
from lang3s.models import Embedder
from lang3s.services.embeddings import embedder

# --- CONFIG ---
# Crucial: Use the indices AFTER your training set
SPLIT_RANGE = "train[500000:]"
OUTPUT_FILE = "query_test_data.pkl"
BATCH_SIZE = 128


def is_clean(text):
    if not isinstance(text, str): return False
    if len(text) < 5 or len(text) > 1200: return False
    return True


def generate_test_data():
    print(f"Loading MS MARCO ({SPLIT_RANGE})...")
    # Load the EXACT SAME dataset configuration
    ds_marco = load_dataset(
        "sentence-transformers/msmarco-msmarco-MiniLM-L6-v3",
        "triplet",
        split=SPLIT_RANGE
    )

    # 1. Extract raw text
    print("Filtering test data...")
    query_texts = []
    pos_texts = []
    neg_texts = []

    for row in tqdm(ds_marco):
        q = row['query']
        p = row['positive']
        n = row['negative']

        if isinstance(q, list): q = q[0] if len(q) > 0 else ""
        if isinstance(p, list): p = p[0] if len(p) > 0 else ""
        if isinstance(n, list): n = n[0] if len(n) > 0 else ""

        if is_clean(q) and is_clean(p) and is_clean(n):
            query_texts.append(q)
            pos_texts.append(p)
            neg_texts.append(n)

    print(f"✅ Found {len(query_texts)} clean samples.")

    print("Pre-computing Target Vectors (Positive & Negative)...")

    pos_vecs = []
    neg_vecs = []

    # Helper to batch embed
    embedder = Embedder()

    def get_embeddings(text_batch):
        # The Embedder handles tokenization and forward pass internally
        # We assume it returns a list of numpy arrays or a tensor
        with torch.no_grad():
            res = embedder(text_batch, task="nli").sentence_embeddings
            return np.stack(res).astype(np.float32)

    for i in tqdm(range(0, len(pos_texts), BATCH_SIZE)):
        # Batch slices
        p_batch = pos_texts[i: i + BATCH_SIZE]
        n_batch = neg_texts[i: i + BATCH_SIZE]

        # Embed and Store
        pos_vecs.append(get_embeddings(p_batch))
        neg_vecs.append(get_embeddings(n_batch))

    print("Saving to disk...")
    payload = {
        "query_text": query_texts,  # List[str] -> Input for Search Head
        "pos_vecs": np.concatenate(pos_vecs, axis=0),  # Array[N, 384] -> Target for Loss
        "neg_vecs": np.concatenate(neg_vecs, axis=0)  # Array[N, 384] -> Negative for Loss
    }
    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(payload, f)

    print(f"✅ Saved {len(query_texts)} samples to {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_test_data()
