import copy

import numpy as np
import torch
from huggingface_hub.utils.tqdm import tqdm
from sklearn.metrics import (
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader
from transformers import (
    AutoModel,
    AutoTokenizer,  # pyright: ignore[reportPrivateImportUsage]
    get_cosine_schedule_with_warmup,
)

from lang3s.scripts.train_classifier import SentenceClassificationDataset

# -------------------------
# Config / data
# -------------------------

training_data = "/Users/ik/Downloads/thinking_traps.jsonl"

dataset = SentenceClassificationDataset(
    path=training_data,
    data_format="json",
    label="label",
    text="text",
)

num_labels = len(dataset.label2Id)
id2label = dataset.id2label

labels_for_split = np.array([dataset[i]["label"] for i in range(len(dataset))])
indices = np.arange(len(dataset))

# Stratified train / val / test split: 70 / 15 / 15
train_idx, temp_idx, y_train, y_temp = train_test_split(
    indices,
    labels_for_split,
    test_size=0.3,
    stratify=labels_for_split,
    random_state=42,
)

val_idx, test_idx, y_val, y_test = train_test_split(
    temp_idx,
    y_temp,
    test_size=0.5,
    stratify=y_temp,
    random_state=42,
)

print(f"Train size: {len(train_idx)}, Val size: {len(val_idx)}, Test size: {len(test_idx)}")

device = (
    "mps"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    else "cuda"
    if torch.cuda.is_available()
    else "cpu"
)
print(f"Using device: {device}")


# -------------------------
# Models
# -------------------------

class SimpleEmbedder(nn.Module):
    def __init__(self, model_name: str = "FacebookAI/roberta-base", device: str = device):
        super().__init__()
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(device)
        self.dimensions: int = self.model.config.hidden_size

    def forward(self, texts):
        encodings = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            return_tensors="pt",
        ).to(self.device)

        outputs = self.model(**encodings)

        # CLS embedding (RoBERTa uses first token <s>)
        token_embeddings = outputs.last_hidden_state
        cls_embeddings = token_embeddings[:, 0]  # (batch, hidden)

        return cls_embeddings


class BinaryOvRClassifier(nn.Module):
    """
    One-vs-rest head with shared trunk and BCEWithLogitsLoss.
    """

    def __init__(self, hidden_size: int, num_labels: int, dropout_prob: float = 0.2):
        super().__init__()
        self.norm = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout_prob)

        self.hidden = nn.Linear(hidden_size, hidden_size // 2)
        self.act = nn.GELU()
        self.dropout2 = nn.Dropout(dropout_prob)

        self.out = nn.Linear(hidden_size // 2, num_labels)

    def forward(self, x):
        x = self.norm(x)
        x = self.dropout(x)
        x = self.hidden(x)
        x = self.act(x)
        x = self.dropout2(x)
        logits = self.out(x)  # (batch, num_labels)
        return logits


# -------------------------
# Training / evaluation helpers
# -------------------------

def _train_one_epoch(
    dataloader: DataLoader,
    embedder: SimpleEmbedder,
    classifier: BinaryOvRClassifier,
    optimizer: torch.optim.Optimizer,
    scheduler,
    device: str,
) -> float:
    classifier.train()
    embedder.train()

    total_loss = 0.0
    for batch in tqdm(dataloader):
        texts = batch["text"]
        labels = batch["label"].to(device)

        # One-vs-rest targets: (batch, num_labels)
        multi_targets = F.one_hot(labels, num_classes=num_labels).float()

        cls_embeddings = embedder(texts)
        logits = classifier(cls_embeddings)

        loss = F.binary_cross_entropy_with_logits(logits, multi_targets)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(classifier.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / max(1, len(dataloader))


def _eval_loss(
    dataloader: DataLoader,
    embedder: SimpleEmbedder,
    classifier: BinaryOvRClassifier,
    device: str,
) -> float:
    classifier.eval()
    embedder.eval()

    total_loss = 0.0
    with torch.no_grad():
        for batch in dataloader:
            texts = batch["text"]
            labels = batch["label"].to(device)
            multi_targets = F.one_hot(labels, num_classes=num_labels).float()

            cls_embeddings = embedder(texts)
            logits = classifier(cls_embeddings)

            loss = F.binary_cross_entropy_with_logits(logits, multi_targets)
            total_loss += loss.item()

    return total_loss / max(1, len(dataloader))


def predict_logits(
    dataloader: DataLoader,
    embedder: SimpleEmbedder,
    classifier: BinaryOvRClassifier,
    device: str,
):
    classifier.eval()
    embedder.eval()

    all_logits = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            texts = batch["text"]
            labels = batch["label"]

            cls_embeddings = embedder(texts)
            logits = classifier(cls_embeddings)

            all_logits.append(logits.cpu())
            all_labels.append(labels.cpu())

    logits_np = torch.cat(all_logits, dim=0).numpy()
    labels_np = torch.cat(all_labels, dim=0).numpy()
    return logits_np, labels_np


def tune_thresholds(
    probs_val: np.ndarray,
    y_val: np.ndarray,
    num_labels: int,
    grid_size: int = 101,
):
    """
    Tune per-class thresholds on the validation set to maximize F1 (binary OvR).
    probs_val: (n_val, num_labels) after sigmoid
    y_val: (n_val,) integer labels
    """
    thresholds = {}
    for c in range(num_labels):
        true_binary = (y_val == c).astype(int)
        best_f1 = 0.0
        best_t = 0.5

        # Skip if class never appears in val
        if true_binary.sum() == 0:
            thresholds[c] = 0.5
            continue

        for t in np.linspace(0.0, 1.0, grid_size):
            pred_binary = (probs_val[:, c] >= t).astype(int)
            _, _, f1, _ = precision_recall_fscore_support(
                true_binary,
                pred_binary,
                average="binary",
                zero_division=0,
            )
            if f1 > best_f1:
                best_f1 = f1
                best_t = t

        thresholds[c] = best_t
        print(f"Class {c} ({id2label[c]}): best threshold={best_t:.3f}, best F1={best_f1:.4f}")

    return thresholds


# -------------------------
# DataLoaders
# -------------------------

train_subset = torch.utils.data.Subset(dataset, train_idx.tolist())
val_subset = torch.utils.data.Subset(dataset, val_idx.tolist())
test_subset = torch.utils.data.Subset(dataset, test_idx.tolist())

batch_size = 8

train_loader = DataLoader(train_subset, batch_size=batch_size, shuffle=True)
val_loader = DataLoader(val_subset, batch_size=batch_size, shuffle=False)
test_loader = DataLoader(test_subset, batch_size=batch_size, shuffle=False)

# -------------------------
# Training loop with early stopping
# -------------------------

num_epochs = 20
lr = 1e-4
warmup_frac = 0.1
patience = 3
min_delta = 1e-3  # minimum improvement in val loss to reset patience

embedder = SimpleEmbedder(device=device)
classifier = BinaryOvRClassifier(hidden_size=embedder.dimensions, num_labels=num_labels).to(device)

optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr)
total_steps = len(train_loader) * num_epochs
warmup_steps = int(warmup_frac * total_steps)

scheduler = get_cosine_schedule_with_warmup(
    optimizer,
    num_warmup_steps=warmup_steps,
    num_training_steps=total_steps,
)

best_val_loss = float("inf")
best_state = None
patience_counter = 0

for epoch in range(num_epochs):
    print(f"\n===== Epoch {epoch + 1}/{num_epochs} =====")
    train_loss = _train_one_epoch(
        train_loader,
        embedder,
        classifier,
        optimizer,
        scheduler,
        device,
    )
    val_loss = _eval_loss(val_loader, embedder, classifier, device)

    print(f"Train loss: {train_loss:.4f} | Val loss: {val_loss:.4f}")

    if val_loss < best_val_loss - min_delta:
        best_val_loss = val_loss
        best_state = copy.deepcopy(classifier.state_dict())
        patience_counter = 0
        print("  -> New best model, resetting patience.")
    else:
        patience_counter += 1
        print(f"  -> No significant improvement. Patience {patience_counter}/{patience}")
        if patience_counter >= patience:
            print("Early stopping triggered.")
            break

# Load best classifier state
if best_state is not None:
    classifier.load_state_dict(best_state)
else:
    print("Warning: no best_state saved, using last epoch weights.")

# -------------------------
# Threshold tuning (on validation set)
# -------------------------

logits_val, y_val = predict_logits(val_loader, embedder, classifier, device)
probs_val = torch.sigmoid(torch.tensor(logits_val)).numpy()

print("\n===== TUNING THRESHOLDS ON VALIDATION SET =====")
thresholds = tune_thresholds(probs_val, y_val, num_labels=num_labels, grid_size=101)

# -------------------------
# Final evaluation on test set
# -------------------------

logits_test, y_test = predict_logits(test_loader, embedder, classifier, device)
probs_test = torch.sigmoid(torch.tensor(logits_test)).numpy()

# Baseline argmax predictions (just to see multiclass accuracy)
y_pred_argmax = np.argmax(probs_test, axis=1)
acc_argmax = (y_pred_argmax == y_test).mean()
print(f"\nArgmax multiclass accuracy on test: {acc_argmax:.4f}")

# OvR predictions using tuned thresholds (multi-label view)
y_true_binary = F.one_hot(torch.tensor(y_test), num_classes=num_labels).numpy()  # (n_test, num_labels)
y_pred_binary = np.zeros_like(y_true_binary)

for c in range(num_labels):
    t = thresholds.get(c, 0.5)
    y_pred_binary[:, c] = (probs_test[:, c] >= t).astype(int)

# Per-class metrics using tuned thresholds
print("\n===== PER-CLASS METRICS (TEST, TUNED THRESHOLDS) =====")
per_class_prec = []
per_class_rec = []
per_class_f1 = []
per_class_auc = []

for c in range(num_labels):
    true_binary = y_true_binary[:, c]
    pred_binary = y_pred_binary[:, c]

    prec, rec, f1, _ = precision_recall_fscore_support(
        true_binary,
        pred_binary,
        average="binary",
        zero_division=0,
    )

    # AUC for this class
    try:
        auc = roc_auc_score(true_binary, probs_test[:, c])
    except ValueError:
        auc = float("nan")

    per_class_prec.append(prec)
    per_class_rec.append(rec)
    per_class_f1.append(f1)
    per_class_auc.append(auc)

    print(
        f"Class {c} ({id2label[c]}): "
        f"P={prec:.4f}, R={rec:.4f}, F1={f1:.4f}, AUC={auc:.4f}, thr={thresholds[c]:.3f}"
    )

per_class_prec = np.array(per_class_prec)
per_class_rec = np.array(per_class_rec)
per_class_f1 = np.array(per_class_f1)
per_class_auc = np.array(per_class_auc)

print("\n===== MACRO AVERAGES (TEST, TUNED THRESHOLDS) =====")
print(f"Macro Precision: {per_class_prec.mean():.4f}")
print(f"Macro Recall   : {per_class_rec.mean():.4f}")
print(f"Macro F1       : {per_class_f1.mean():.4f}")
print(f"Macro AUC      : {np.nanmean(per_class_auc):.4f}")

# Global micro/macro F1 across all classes (multi-label view)
micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
    y_true_binary,
    y_pred_binary,
    average="micro",
    zero_division=0,
)
macro_p, macro_r, macro_f1_global, _ = precision_recall_fscore_support(
    y_true_binary,
    y_pred_binary,
    average="macro",
    zero_division=0,
)

print("\n===== GLOBAL MICRO / MACRO (OVR, TEST) =====")
print(f"Micro  P={micro_p:.4f}, R={micro_r:.4f}, F1={micro_f1:.4f}")
print(f"Macro  P={macro_p:.4f}, R={macro_r:.4f}, F1={macro_f1_global:.4f}")
