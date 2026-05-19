import pickle
from typing import List

import torch
import torch.nn as nn
import torch.nn.functional as F
from lang3s import config
from lang3s.models.base_transformer_model import ForkedBaseModel
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

# --- CONFIGURATION ---
BATCH_SIZE = 128
LR = 1e-4
EPOCHS = 4
MAX_LEN = 64

SCALE = 20.0  # Crucial temperature scaling for Cosine Similarity
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
if torch.backends.mps.is_available():
    DEVICE = "mps"


# --- 1. DATASET ---
class QueryDistillationDataset(Dataset):
    def __init__(self, data_path):
        with open(data_path, "rb") as f:
            data = pickle.load(f)
        self.anchors: List[str] = data["anchors"]
        self.pos_embs = torch.from_numpy(data["positive_embeddings"]).float()
        self.neg_embs = torch.from_numpy(
            data["negative_embeddings"]
        ).float()  # Load Negatives!

    def __len__(self):
        return len(self.anchors)

    def __getitem__(self, idx):
        return {
            "query": self.anchors[idx],
            "target_vec": self.pos_embs[idx],
            "negative_vec": self.neg_embs[idx],  # Return Negatives!
        }


class CosineTripletLoss(nn.Module):
    def __init__(self, margin=0.2):
        super().__init__()
        self.margin = margin

    def forward(self, query, positive, negative):
        # Cosine Similarity: Range [-1, 1] (Higher is better)
        sim_pos = F.cosine_similarity(query, positive)
        sim_neg = F.cosine_similarity(query, negative)

        # Loss = max(0, sim_neg - sim_pos + margin)
        # We want sim_pos > sim_neg + margin
        loss = torch.relu(sim_neg - sim_pos + self.margin)
        return loss.mean()


class MNRLWithHardNegatives(nn.Module):
    def forward(self, q, p, n):
        # C. Construct Candidate Pool (Positives + Negatives)
        # Shape: [2 * B, 384]
        candidates = torch.cat([p, n], dim=0)
        # D. Compute Similarity Matrix
        # Query (B) x Candidates (2B) -> Scores (B, 2B)
        scores = torch.matmul(q, p.transpose(0, 1)) * SCALE

        # E. Labels
        # The correct answer for Query[i] is Candidate[i] (which is Positive[i])
        # The indices 0..B-1 are the correct targets.
        labels = torch.arange(BATCH_SIZE, device=DEVICE)

        # F. Loss
        return F.cross_entropy(scores, labels)


# --- 3. TRAINING LOOP ---
def train():
    print(f"Loading Data on {DEVICE}...")
    dataset = QueryDistillationDataset("query_training_data.pkl")
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)

    tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
    model = ForkedBaseModel(config.EMBEDDING_MODEL)
    model.to(DEVICE)
    model.train()
    for p in model.parameters():
        p.requires_grad = False
    for p in model.search_layers.parameters():
        p.requires_grad = True
    for p in model.search_compression.parameters():
        p.requires_grad = True

    trainable_params = list(model.search_layers.parameters()) + list(
        model.search_compression.parameters()
    )
    optimizer = torch.optim.AdamW(trainable_params, lr=LR)
    # criterion = CosineTripletLoss(margin=0.2)  # Margin of 0.2 is standard for cosine
    criterion = MNRLWithHardNegatives()

    total_steps = len(loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * total_steps),
        num_training_steps=total_steps,
    )
    mse_loss = nn.MSELoss()
    print("Starting MNRL Training...")

    for epoch in range(EPOCHS):
        loop = tqdm(loader, desc=f"Epoch {epoch + 1}/{EPOCHS}")
        total_loss = 0
        for batch in loop:
            # A. Get Data
            q = [t.lower() for t in batch["query"]]  # [B, 384]
            p = batch["target_vec"].to(DEVICE)  # [B, 384]
            n = batch["negative_vec"].to(DEVICE)  # [B, 384]

            # Normalize Targets
            # B. Forward Pass
            p = F.normalize(p, p=2, dim=1)
            n = F.normalize(n, p=2, dim=1)

            inputs = tokenizer(
                q,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=MAX_LEN,
            ).to(DEVICE)
            outputs = model(**inputs, task="search")
            last_hidden_state = outputs["semantic_head"]
            compressor = outputs["compressor"]

            mask = (
                inputs["attention_mask"]
                .unsqueeze(-1)
                .expand(last_hidden_state.size())
                .float()
            )
            sum_embeddings = torch.sum(last_hidden_state * mask, 1)
            sum_mask = torch.clamp(mask.sum(1), min=1e-9)
            sent_768 = sum_embeddings / sum_mask
            sent_compressed = compressor(sent_768)  # 368-d
            q_out = torch.nn.functional.normalize(sent_compressed, p=2, dim=1)

            loss = criterion(q_out, p, n) + mse_loss(q_out, p)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            total_loss += loss
            loop.set_postfix(loss=f"{loss.item():.4f}")
        print(f"Epoch {epoch + 1}: average_loss={total_loss / len(loader):.4f}")

    # Save
    torch.save(model.search_layers.state_dict(), "search_layers.pt")
    torch.save(model.search_compression.state_dict(), "search_compressed.pt")
    print("✅ Saved search model")


if __name__ == "__main__":
    train()
