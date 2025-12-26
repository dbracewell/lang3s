import pickle

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from lang3s.models import Embedder

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class TestDataset(Dataset):
    def __init__(self, path):
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.q = data["query_text"]
        self.p = torch.from_numpy(data['pos_vecs']).float()
        self.n = torch.from_numpy(data['neg_vecs']).float()

    def __len__(self): return len(self.q)

    def __getitem__(self, i): return self.q[i], self.p[i], self.n[i]


def short_test():
    # 1. Setup Data
    query_text = "George Bush"

    # The "Distractors" (High semantic similarity, but wrong fact)
    distractors = [
        "It's really incredible - to get the winning point is really something.",
        "But certainly I think we can put the work in at the appropriate time.",
        "What a great way to finish the year,"
    ]

    # The "Target" (The actual fact we want)
    targets = [
        "The official re-election site of President George W Bush is blocking visits.",
        "Tony Blair has said he looks forward to continuing his strong relationship with George Bush."
    ]

    corpus = distractors + targets

    # 2. Load Models
    embedder = Embedder()  # Your fine-tuned 384d student

    # 3. Create Index (Passage Space)
    # We ALWAYS use the base embedder for documents (Frozen)
    print("Encoding Corpus...")
    corpus_embeddings = embedder(corpus, task="nli").sentence_embeddings  # List of numpy arrays
    corpus_matrix = np.stack(corpus_embeddings)  # [N, 384]

    # 4. Encode Query (The A/B Test)
    print(f"\nQuerying: '{query_text}'")

    # --- A. BASE MODEL (No Adapter) ---
    base_q = embedder([query_text.lower()], task="nli").sentence_embeddings[0]  # [384]
    adapted_q = embedder([query_text], task="search").sentence_embeddings[0]  # [384]
    scores_base = np.dot(corpus_matrix, base_q)
    scores_adapted = np.dot(corpus_matrix, adapted_q)

    # 5. Print Comparison
    def print_rank(scores, title):
        print(f"\n--- {title} ---")
        # Sort indices by score descending
        ranked_indices = np.argsort(scores)[::-1]

        for rank, idx in enumerate(ranked_indices):
            score = scores[idx]
            text = corpus[idx]
            is_target = text in targets
            # Mark targets with ✅, distractors with ❌
            mark = "✅" if is_target else "❌"
            print(f"{rank + 1}. [{score:.4f}] {mark} {text[:60]}...")

    print_rank(scores_base, "BEFORE (Base Model)")
    print_rank(scores_adapted, "AFTER (Query Head)")


def evaluate():
    print("Loading Test Data...")
    ds = TestDataset("query_test_data.pkl")
    loader = DataLoader(ds, batch_size=128, shuffle=False)

    # Load Model
    model = Embedder()

    correct = 0
    total = 0

    print("Running Evaluation...")
    with torch.no_grad():
        for q_raw, p_raw, n_raw in tqdm(loader):
            p_raw = p_raw.to(DEVICE)
            n_raw = n_raw.to(DEVICE)

            q_adapted = torch.tensor(np.array(model(q_raw, task="search").sentence_embeddings)).to(DEVICE)
            p_raw = F.normalize(p_raw, p=2, dim=1)
            n_raw = F.normalize(n_raw, p=2, dim=1)

            # 3. Calculate Scores
            # Dot product of normalized vectors = Cosine Similarity
            score_pos = (q_adapted * p_raw).sum(dim=1)
            score_neg = (q_adapted * n_raw).sum(dim=1)

            # 4. Count Correct
            # Correct if Positive Score > Negative Score
            correct += (score_pos > score_neg).sum().item()
            total += len(q_raw)

    acc = correct / total
    print(f"\n✅ Test Set Accuracy: {acc:.2%}")
    print(f"   (Random guessing would be 50.00%)")


if __name__ == "__main__":
    short_test()
    # evaluate()
