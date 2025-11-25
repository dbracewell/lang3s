import copy

import numpy as np
import torch
from huggingface_hub.utils.tqdm import tqdm
from sklearn.metrics import (
    precision_recall_fscore_support
)
from sklearn.model_selection import train_test_split
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader
from transformers import (
    AutoTokenizer,
    AutoModel,
    get_cosine_schedule_with_warmup,
)

from lang3s.models.transformer.shared_types import TaskType
from lang3s.scripts.train_classifier import SentenceClassificationDataset

# ============================================================
# Config
# ============================================================

training_data = "/Users/ik/Downloads/data/thinking_traps_augmented.jsonl"

EPOCHS = 50
BATCH_SIZE = 8
LR = 2e-5  # lower lr works better for mental-roberta
WARMUP_FRAC = 0.1
FREEZE_WARMUP_EPOCHS = 3  # freeze lower layers early on
PATIENCE = 5  # for macro-F1 early stopping
DEVICE = (
    "mps"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    else "cuda" if torch.cuda.is_available()
    else "cpu"
)

print("Using device:", DEVICE)

# ============================================================
# Dataset
# ============================================================

dataset = SentenceClassificationDataset(
    task_type=TaskType.SENTENCE,
    path=training_data,
    data_format="json",
    label="label",
    text="text",
)

labels = np.array([dataset[i]["label"] for i in range(len(dataset))])
num_labels = len(dataset.label2idx)
id2label = dataset.idx2label

# split 70/15/15
indices = np.arange(len(dataset))
train_idx, temp_idx, y_train, y_temp = train_test_split(
    indices, labels, test_size=0.30, stratify=labels, random_state=42
)
val_idx, test_idx, y_val, y_test = train_test_split(
    temp_idx, y_temp, test_size=0.50, stratify=y_temp, random_state=42
)

train_ds = torch.utils.data.Subset(dataset, train_idx)
val_ds = torch.utils.data.Subset(dataset, val_idx)
test_ds = torch.utils.data.Subset(dataset, test_idx)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False)


# ============================================================
# Focal Loss (Multiclass)
# ============================================================

class FocalLoss(nn.Module):
    def __init__(self, gamma=2, weight=None, reduction='mean'):
        super().__init__()
        self.gamma = gamma
        self.weight = weight
        self.reduction = reduction

    def forward(self, logits, targets):
        ce_loss = F.cross_entropy(logits, targets, weight=self.weight, reduction='none')
        pt = torch.exp(-ce_loss)
        loss = ((1 - pt) ** self.gamma) * ce_loss
        return loss.mean()


# ============================================================
# Models
# ============================================================

class SimpleEmbedder(nn.Module):
    def __init__(self, model_name="mental/mental-roberta-base", device=DEVICE):
        super().__init__()
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device)
        self.dim = self.model.config.hidden_size

    def forward(self, texts):
        enc = self.tokenizer(
            texts, truncation=True, padding=True, return_tensors="pt"
        ).to(self.device)
        out = self.model(**enc)
        cls = out.last_hidden_state[:, 0]
        return cls


class DeepClassifier(nn.Module):
    """
    Stronger classification head:
    LN -> Dropout -> Linear -> GELU ->
    Dropout -> Linear -> GELU -> Dropout -> Out
    """

    def __init__(self, hidden, num_labels, dropout=0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.GELU(),

            nn.Dropout(dropout),
            nn.Linear(hidden, hidden // 2),
            nn.GELU(),

            nn.Dropout(dropout),
            nn.Linear(hidden // 2, num_labels)
        )

    def forward(self, x):
        return self.net(x)


embedder = SimpleEmbedder()
classifier = DeepClassifier(embedder.dim, num_labels).to(DEVICE)

# ============================================================
# Optimizer, Scheduler, Weights
# ============================================================

# class weights to fix imbalance
counts = np.bincount(labels)
weights = torch.tensor(1.0 / np.maximum(counts, 1), dtype=torch.float32)
weights = weights / weights.mean()
weights = weights.to(DEVICE)

loss_fn = FocalLoss(gamma=2, weight=weights)

optimizer = torch.optim.AdamW(
    list(classifier.parameters()) + list(embedder.parameters()),
    lr=LR
)

total_steps = len(train_loader) * EPOCHS
warmup_steps = int(WARMUP_FRAC * total_steps)

scheduler = get_cosine_schedule_with_warmup(
    optimizer,
    num_warmup_steps=warmup_steps,
    num_training_steps=total_steps
)


# ============================================================
# Training/Eval Helpers
# ============================================================

def freeze_lower_layers(model, freeze=True):
    """
    Freeze the *bottom 6* transformer layers to prevent overfitting
    at the start of training.
    """
    try:
        for i, layer in enumerate(model.model.encoder.layer):
            if i < 6:
                for param in layer.parameters():
                    param.requires_grad = not freeze
    except:
        pass


def train_one_epoch(epoch):
    embedder.train()
    classifier.train()

    if epoch < FREEZE_WARMUP_EPOCHS:
        freeze_lower_layers(embedder, freeze=True)
    else:
        freeze_lower_layers(embedder, freeze=False)

    total_loss = 0.0
    for batch in tqdm(train_loader):
        texts = batch["text"]
        labels = batch["label"].to(DEVICE)

        cls = embedder(texts)
        logits = classifier(cls)
        loss = loss_fn(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(classifier.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(train_loader)


def evaluate(loader):
    embedder.eval()
    classifier.eval()

    all_logits = []
    all_labels = []

    with torch.no_grad():
        for batch in loader:
            texts = batch["text"]
            labels = batch["label"]

            cls = embedder(texts)
            logits = classifier(cls)

            all_logits.append(logits.cpu())
            all_labels.append(labels.cpu())

    logits = torch.cat(all_logits).numpy()
    labels = torch.cat(all_labels).numpy()
    preds = np.argmax(logits, axis=1)

    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, labels=list(range(num_labels)), zero_division=0
    )

    macro_f1 = f1.mean()
    return macro_f1, logits, labels, preds, prec, rec, f1


# ============================================================
# Training Loop with Macro-F1 Early Stopping
# ============================================================

best_macro_f1 = -1
best_state = None
patience_cnt = 0

for epoch in range(EPOCHS):
    print(f"\n===== Epoch {epoch + 1}/{EPOCHS} =====")
    train_loss = train_one_epoch(epoch)
    val_macro_f1, _, _, _, _, _, _ = evaluate(val_loader)

    print(f"Train Loss: {train_loss:.4f}  |  Val Macro F1: {val_macro_f1:.4f}")

    if val_macro_f1 > best_macro_f1 + 1e-4:
        best_macro_f1 = val_macro_f1
        best_state = {
            "embedder": copy.deepcopy(embedder.state_dict()),
            "classifier": copy.deepcopy(classifier.state_dict())
        }
        patience_cnt = 0
        print("  -> New best model saved.")
    else:
        patience_cnt += 1
        print(f"  -> No improvement ({patience_cnt}/{PATIENCE})")
        if patience_cnt >= PATIENCE:
            print("Early stopping!")
            break

# Load best weights
embedder.load_state_dict(best_state["embedder"])
classifier.load_state_dict(best_state["classifier"])

# ============================================================
# Final Test Evaluation
# ============================================================

macro_f1, logits, labels, preds, prec, rec, f1 = evaluate(test_loader)

acc = (preds == labels).mean()
print("\n===== FINAL TEST RESULTS =====")
print(f"Accuracy: {acc:.4f}")
print(f"Macro F1: {macro_f1:.4f}")

print("\n===== PER-CLASS METRICS =====")
for c in range(num_labels):
    print(
        f"Class {c} ({id2label[c]}): "
        f"P={prec[c]:.4f}, R={rec[c]:.4f}, F1={f1[c]:.4f}"
    )
