from typing import Dict, Any, List, Optional, Tuple

import torch
import torch.nn as nn
from sklearn.metrics import precision_recall_fscore_support
from torch.utils.data import random_split, Dataset, DataLoader
from torchcrf import CRF
from transformers import AutoTokenizer, AutoModel


def bio_to_spans(labels: List[str]) -> List[Tuple[str, int, int]]:
    """
    Convert BIO tags into spans.

    Returns:
        List of (type, start, end) inclusive ranges
    """
    spans = []
    start = None
    entity_type = None

    for i, tag in enumerate(labels):

        if tag == "O":
            # If we were inside a chunk, close it
            if entity_type is not None:
                spans.append((entity_type, start, i - 1))
                entity_type = None
                start = None
            continue

        prefix, chunk_type = tag.split("-", 1)

        if prefix == "B":
            # Close previous chunk
            if entity_type is not None:
                spans.append((entity_type, start, i - 1))

            # Start new chunk
            entity_type = chunk_type
            start = i

        elif prefix == "I":
            # Continue only if same type, otherwise start new
            if entity_type != chunk_type:
                if entity_type is not None:
                    spans.append((entity_type, start, i - 1))
                entity_type = chunk_type
                start = i

    # Close any open span
    if entity_type is not None:
        spans.append((entity_type, start, len(labels) - 1))

    return spans


def compute_span_f1(all_gold, all_pred):
    """
    Compute span-level (chunk-level) precision, recall, F1.
    """
    gold_spans = []
    pred_spans = []

    for gold_seq, pred_seq in zip(all_gold, all_pred):
        gold_spans.extend(bio_to_spans(gold_seq))
        pred_spans.extend(bio_to_spans(pred_seq))

    gold_set = set(gold_spans)
    pred_set = set(pred_spans)

    tp = len(gold_set & pred_set)
    fp = len(pred_set - gold_set)
    fn = len(gold_set - pred_set)

    precision = tp / (tp + fp + 1e-9)
    recall = tp / (tp + fn + 1e-9)
    f1 = 2 * precision * recall / (precision + recall + 1e-9)

    return precision, recall, f1


def compute_precision_recall_f1(
    all_gold: List[List[str]],
    all_pred: List[List[str]],
    labels: List[str],
):
    """
    Computes macro precision/recall/f1 over tokens (word-level).
    """
    gold_flat = []
    pred_flat = []

    for g_seq, p_seq in zip(all_gold, all_pred):
        for g, p in zip(g_seq, p_seq):
            gold_flat.append(g)
            pred_flat.append(p)

    precision, recall, f1, _ = precision_recall_fscore_support(
        gold_flat,
        pred_flat,
        labels=labels,
        average="macro",
        zero_division=0,
    )

    return precision, recall, f1


# ============================================================
# Dataset
# ============================================================

class CoNLLDataset(Dataset):
    """
    A simple dataset for reading CoNLL format files.

    Assumes:
        token = first column
        label = last column
        sentences separated by blank lines
    """

    def __init__(self, path: str):
        self.sentences: List[Tuple[List[str], List[str]]] = []
        self.label2idx: Dict[str, int] = {}
        self.idx2label: Dict[int, str] = {}

        self._read_conll(path)

    def _read_conll(self, path: str):
        tokens: List[str] = []
        labels: List[str] = []
        all_labels = set()

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Sentence boundary
                if not line:
                    if tokens:
                        self.sentences.append((tokens, labels))
                        tokens, labels = [], []
                    continue

                cols = line.split()
                token = cols[0]
                label = cols[-1]
                all_labels.add(label)

                tokens.append(token)
                labels.append(label)

        # Capture last sentence if file does not end with blank line
        if tokens:
            self.sentences.append((tokens, labels))

        # Build stable label mappings, with "O" first if present
        all_labels = sorted(all_labels)
        if "O" in all_labels:
            all_labels.remove("O")
            all_labels = ["O"] + all_labels

        self.label2idx = {lbl: idx for idx, lbl in enumerate(all_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx: int):
        tokens, labels = self.sentences[idx]
        return tokens, labels


def token_classification_collate(batch):
    # batch: List[Tuple[List[str], List[str]]]
    texts = [sample[0] for sample in batch]
    labels = [sample[1] for sample in batch]
    return {
        "text": texts,
        "label": labels,
    }


# ============================================================
# Embedder
# ============================================================

class SimpleEmbedder(nn.Module):
    def __init__(self, model_name: str = "xlm-roberta-base", device: Optional[str] = None):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)

        # freeze params
        for p in self.model.parameters():
            p.requires_grad = False

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.model = self.model.to(self.device)

    @torch.no_grad()
    def encode(self, batch_tokens: List[List[str]]) -> Dict[str, Any]:
        encoded = self.tokenizer(
            batch_tokens,
            is_split_into_words=True,
            return_tensors="pt",
            padding=True,
            truncation=True,
            return_attention_mask=True,
        ).to(self.device)

        # Forward pass (B, T, H)
        embeddings = self.model(**encoded).last_hidden_state

        # Convert word ids for each batch element
        word_ids_batch = []
        for i in range(len(batch_tokens)):
            word_ids_batch.append(encoded.word_ids(batch_index=i))

        return {
            "token_embeddings": embeddings,  # [B, T, H]
            "word_ids": word_ids_batch,  # List[List[int or None]]
            "attention_mask": encoded["attention_mask"],  # [B, T]
        }


# ============================================================
# Batch Preparation
# ============================================================

def prepare_batch_for_bilstm_crf(
    batch: Dict[str, List[List[str]]],
    embedder: SimpleEmbedder,
    label2id: Dict[str, int],
    pad_label: str = "O",
) -> Dict[str, torch.Tensor]:
    """
    Take a batch from the DataLoader and produce:
        - embeddings [B, T, H]
        - labels     [B, T]
        - mask       [B, T]

    Args:
        batch:
            {
              "text":  List[List[str]],
              "label": List[List[str]]
            }
        embedder: SimpleEmbedder instance
        label2id: mapping from str -> int
        pad_label: label used for padding (default "O")

    Returns:
        dict with:
            embeddings: [B, T, H]
            labels:     [B, T]
            mask:       [B, T]  (bool)
    """

    sentences = batch["text"]  # List[List[str]]
    gold_labels = batch["label"]  # List[List[str]]

    # Step 1: run embedder
    encoded = embedder.encode(sentences)
    embeddings = encoded["token_embeddings"]  # [B, T, H]
    word_ids_batch = encoded["word_ids"]  # List[List[int or None]]
    attention_mask = encoded["attention_mask"].bool()  # [B, T]

    B, T, H = embeddings.size()

    # Step 2: build label tensor aligned to subwords
    aligned_labels = torch.full(
        (B, T),
        fill_value=label2id[pad_label],
        dtype=torch.long,
        device=embeddings.device,
    )

    # We'll use attention_mask as CRF mask (all non-pad tokens)
    mask = attention_mask.clone()  # [B, T] bool

    # Fill aligned labels
    for b in range(B):
        word_ids = word_ids_batch[b]  # list of word indices per subword
        labels = gold_labels[b]  # original token-level labels

        for subword_idx, word_id in enumerate(word_ids):
            if word_id is None:
                # special tokens (<s>, </s>) → keep pad_label ("O")
                continue

            if word_id < len(labels):
                aligned_labels[b, subword_idx] = label2id[labels[word_id]]
            else:
                # Should not happen, but be safe
                aligned_labels[b, subword_idx] = label2id[pad_label]

    # CRF requires mask[:, 0] == True
    # attention_mask already does this for <s>, so we are good.

    return {
        "embeddings": embeddings,  # [B, T, H]
        "labels": aligned_labels,  # [B, T]
        "mask": mask,  # [B, T]
    }


# ============================================================
# BiLSTM + CRF Head
# ============================================================

class BiLSTMCRFClassifierHead(nn.Module):
    """
    A BiLSTM + Linear layer + CRF for token classification.

    Expects:
        token_embeddings: [B, T, H]
        mask: [B, T] boolean mask
        labels: [B, T] (optional during training)
    """

    def __init__(
        self,
        embedding_dim: int,
        hidden_size: int,
        num_labels: int,
        num_lstm_layers: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_size,
            num_layers=num_lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_lstm_layers > 1 else 0.0,
        )

        self.dropout = nn.Dropout(dropout)
        self.hidden2tag = nn.Linear(hidden_size * 2, num_labels)

        # CRF expects emission scores [B, T, num_labels]
        self.crf = CRF(num_tags=num_labels, batch_first=True)

    def forward(
        self,
        token_embeddings: torch.Tensor,  # [B, T, H]
        mask: torch.Tensor,  # [B, T] bool
        labels: Optional[torch.Tensor] = None,  # [B, T]
    ):
        # BiLSTM
        lstm_out, _ = self.lstm(token_embeddings)  # [B, T, 2H]
        lstm_out = self.dropout(lstm_out)

        # Project to num_labels
        emissions = self.hidden2tag(lstm_out)  # [B, T, num_labels]

        if labels is not None:
            # CRF loss (negative log-likelihood)
            log_likelihood = self.crf(emissions, labels, mask=mask, reduction="mean")
            return -log_likelihood  # return loss

        # Inference: returns best path
        best_paths = self.crf.decode(emissions, mask=mask)
        return best_paths


# ============================================================
# Training / Evaluation Utilities
# ============================================================

def print_predictions(texts, gold, pred):
    for tokens, gold_seq, pred_seq in zip(texts, gold, pred):
        print("Tokens:     ", " ".join(tokens))
        print("Gold:       ", " ".join(gold_seq))
        print("Predicted:  ", " ".join(pred_seq))
        print("-" * 80)


def train_one_epoch(
    epoch: int,
    dataloader: DataLoader,
    embedder: SimpleEmbedder,
    clf: BiLSTMCRFClassifierHead,
    label2idx: Dict[str, int],
    pad_label: str,
    optimizer: torch.optim.Optimizer,
):
    clf.train()
    total_loss = 0.0

    for batch_idx, batch in enumerate(dataloader):
        batch_inputs = prepare_batch_for_bilstm_crf(
            batch,
            embedder=embedder,
            label2id=label2idx,
            pad_label=pad_label,
        )

        emb = batch_inputs["embeddings"]
        labels = batch_inputs["labels"]
        mask = batch_inputs["mask"]

        loss = clf(
            token_embeddings=emb,
            labels=labels,
            mask=mask,
        )

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(clf.parameters(), 5.0)
        optimizer.step()

        total_loss += loss.item()

        if batch_idx % 10 == 0:
            print(f"[Epoch {epoch}] Step {batch_idx} Loss: {loss.item():.4f}")

    avg_loss = total_loss / len(dataloader)
    print(f"Epoch {epoch} Train Loss: {avg_loss:.4f}")
    return avg_loss


def eval_one_epoch(
    epoch: int,
    dataloader: DataLoader,
    embedder: SimpleEmbedder,
    clf: BiLSTMCRFClassifierHead,
    label2idx: Dict[str, int],
    idx2label: Dict[int, str],
    pad_label: str,
    print_samples: bool = True,
):
    clf.eval()
    total_loss = 0.0
    all_gold = []
    all_pred = []
    all_text = []

    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            batch_inputs = prepare_batch_for_bilstm_crf(
                batch,
                embedder=embedder,
                label2id=label2idx,
                pad_label=pad_label,
            )

            emb = batch_inputs["embeddings"]
            labels = batch_inputs["labels"]
            mask = batch_inputs["mask"]

            loss = clf(
                token_embeddings=emb,
                labels=labels,
                mask=mask,
            )
            total_loss += loss.item()

            # CRF decoding
            pred_paths = clf(
                token_embeddings=emb,
                mask=mask,
                labels=None,
            )

            # Align predictions back to word-level using word_ids
            sentences = batch["text"]
            gold_labels_batch = batch["label"]
            encoded = embedder.encode(sentences)
            word_ids_batch = encoded["word_ids"]

            for i, (tokens, gold_seq, word_ids) in enumerate(
                zip(sentences, gold_labels_batch, word_ids_batch)
            ):
                # word-level gold is already correct
                gold_seq_word = gold_seq

                # predicted word-level labels: take first subword's prediction for each token
                pred_seq_word: List[str] = []
                for word_idx in range(len(tokens)):
                    # all positions where this word appears
                    sub_positions = [j for j, w in enumerate(word_ids) if w == word_idx]
                    if not sub_positions:
                        pred_seq_word.append(pad_label)
                        continue
                    sub0 = sub_positions[0]
                    pred_label_id = pred_paths[i][sub0]
                    pred_seq_word.append(idx2label[pred_label_id])

                all_text.append(tokens)
                all_gold.append(gold_seq_word)
                all_pred.append(pred_seq_word)

    avg_loss = total_loss / len(dataloader)
    print(f"Epoch {epoch} Val Loss: {avg_loss:.4f}")

    if print_samples:
        print("\n--- SAMPLE PREDICTIONS ---")
        for i in range(min(3, len(all_text))):
            print_predictions([all_text[i]], [all_gold[i]], [all_pred[i]])

    sorted_labels = list(idx2label.values())
    precision, recall, f1 = compute_precision_recall_f1(
        all_gold, all_pred, sorted_labels
    )

    print(f"Epoch {epoch} Val Precision: {precision:.4f}")
    print(f"Epoch {epoch} Val Recall:    {recall:.4f}")
    print(f"Epoch {epoch} Val F1:        {f1:.4f}")
    span_precision, span_recall, span_f1 = compute_span_f1(all_gold, all_pred)

    print(f"Epoch {epoch} Span Precision: {span_precision:.4f}")
    print(f"Epoch {epoch} Span Recall:    {span_recall:.4f}")
    print(f"Epoch {epoch} Span F1:        {span_f1:.4f}")

    # Print samples
    if print_samples:
        print("\n--- SAMPLE PREDICTIONS ---")
        for i in range(min(3, len(all_text))):
            print_predictions([all_text[i]], [all_gold[i]], [all_pred[i]])

    return avg_loss, precision, recall, f1, span_precision, span_recall, span_f1


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    # Path to your CoNLL file
    data_path = "/Users/ik/prj/Lang3s/backend/nlp/data/phrase_chunk/train.conll"

    # Create dataset
    dataset = CoNLLDataset(data_path)

    # Simple sanity check: ensure pad_label exists
    pad_label = "O"
    if pad_label not in dataset.label2idx:
        raise ValueError(f"pad_label '{pad_label}' not found in dataset labels")

    # Split train / val
    val_size = int(len(dataset) * 0.1)
    train_size = len(dataset) - val_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

    train_dataloader = DataLoader(
        train_dataset,
        batch_size=32,
        shuffle=True,
        collate_fn=token_classification_collate,
    )

    val_dataloader = DataLoader(
        val_dataset,
        batch_size=64,
        shuffle=False,
        collate_fn=token_classification_collate,
    )

    # Embedder
    embedder = SimpleEmbedder(model_name="xlm-roberta-base", device="mps")

    # Classifier head
    clf = BiLSTMCRFClassifierHead(
        embedding_dim=embedder.model.config.hidden_size,
        hidden_size=256,
        num_labels=len(dataset.label2idx),
        dropout=0.1,
    ).to(embedder.device)

    # Optimizer + training params
    lr = 1e-4
    optimizer = torch.optim.AdamW(
        clf.parameters(),
        lr=lr,
        weight_decay=0.01,
    )

    num_epochs = 5
    best_f1 = 0.0
    patience = 3
    patience_counter = 0
    for epoch in range(1, num_epochs + 1):
        train_one_epoch(
            epoch=epoch,
            dataloader=train_dataloader,
            embedder=embedder,
            clf=clf,
            label2idx=dataset.label2idx,
            pad_label=pad_label,
            optimizer=optimizer,
        )

        (
            val_loss,
            token_precision,
            token_recall,
            token_f1,
            span_precision,
            span_recall,
            span_f1,
        ) = eval_one_epoch(
            epoch=epoch,
            dataloader=val_dataloader,
            embedder=embedder,
            clf=clf,
            label2idx=dataset.label2idx,
            idx2label=dataset.idx2label,
            pad_label=pad_label,
            print_samples=True,
        )

        # Early stopping
        if span_f1 > best_f1:
            print(f"Span-F1 improved from {best_f1:.4f} → {span_f1:.4f}. Saving model...")
            best_f1 = span_f1
            patience_counter = 0
            torch.save(clf.state_dict(), "best_model.pt")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print("Early stopping triggered on span-level F1.")
                break
