import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import DataLoader, random_split, Dataset
from torch.utils.data.dataset import Subset
from tqdm import tqdm
from transformers import get_cosine_schedule_with_warmup  # pyright: ignore[reportPrivateImportUsage]
from transformers import get_linear_schedule_with_warmup  # pyright: ignore[reportPrivateImportUsage]

from lang3s import config
from lang3s.models.embedder import Embedder
from lang3s.models.transformer import MultiTaskTransformer
from .shared_types import TaskType
from .task_registry import Task, TaskHead

embedder = Embedder()


def _get_labels_for_split(dataset: Dataset, task_type: TaskType, total_size: int) -> List:
    """
    Extracts labels for stratification based on task type.
    Note: This assumes dataset[i] returns a dictionary with a 'label' key.
    """
    all_labels = []

    # We must iterate over the full dataset to get labels for stratification
    for i in tqdm(range(total_size), desc="Extracting labels for stratification"):
        try:
            label = dataset[i]["label"]

            if task_type == TaskType.SENTENCE:
                all_labels.append(label.item() if isinstance(label, torch.Tensor) else label)

            elif task_type == TaskType.SENTENCE_MULTILABEL:
                label_tuple = tuple(label.tolist() if isinstance(label, torch.Tensor) else label)
                all_labels.append(label_tuple)

            else:
                all_labels.append(None)
        except Exception:
            all_labels.append(None)  # Cannot stratify this sample

    return all_labels


def token_classification_collate(batch):
    texts = [sample["text"] for sample in batch]
    labels = [sample["label"] for sample in batch]
    return {
        "text": texts,
        "label": labels,
    }


def _get_input_and_labels(
    task_type: TaskType,
    batch: Dict[str, Any],
    num_attention_heads: int,
    device: str,
):
    raw_texts = batch["text"]
    raw_labels = batch["label"]  # for token tasks: list[list[int]]
    result = embedder(
        raw_texts,
        is_split_into_words=(task_type == TaskType.TOKEN)
    )

    if task_type.is_sentence_level():
        if num_attention_heads > 0:
            hidden = pad_sequence(
                [torch.as_tensor(e, device=device, dtype=torch.float32) for e in result.word_embeddings],
                batch_first=True,
                padding_value=0,
            ).to(device)
        else:
            hidden = torch.stack(
                [torch.as_tensor(e, device=device, dtype=torch.float32) for e in result.sentence_embeddings],
                dim=0,
            ).to(device)

        if isinstance(raw_labels, torch.Tensor):
            labels = raw_labels.type(torch.long).to(device)
        else:
            labels = torch.tensor(raw_labels, device=device)

        return hidden, labels, None, result

    batch_hidden_unpadded = []
    batch_labels_unpadded = []

    for mapping, word_lbls, tok_emb, text in zip(
        result.mapping, raw_labels, result.token_embeddings, raw_texts
    ):
        word_ids = mapping.word_ids
        # keep only real-word tokens
        keep_idx = [
            i for i, wid in enumerate(word_ids)
            if wid is not None and (i == 0 or wid != word_ids[i - 1])
        ]

        if not keep_idx:
            batch_hidden_unpadded.append(torch.zeros((1, tok_emb.shape[-1]), device=device))
            batch_labels_unpadded.append([0])
            continue

        # slice token embeddings
        real_tok_emb = tok_emb[keep_idx, :]  # numpy array [T, H]
        real_tok_emb = torch.as_tensor(real_tok_emb, dtype=torch.float32, device=device)

        seq_lbls = [word_lbls[word_ids[idx]] for idx in keep_idx]

        assert real_tok_emb.size(0) == len(seq_lbls)

        batch_hidden_unpadded.append(real_tok_emb)
        batch_labels_unpadded.append(seq_lbls)

    batch_max_len = max(len(lbls) for lbls in batch_labels_unpadded)
    batch_hidden = []
    batch_labels = []
    batch_masks = []

    for h, lbls in zip(batch_hidden_unpadded, batch_labels_unpadded):

        T = h.size(0)
        pad_len = batch_max_len - T

        if pad_len > 0:
            # pad embeddings
            pad_block = torch.zeros((pad_len, h.size(1)), device=device)
            h_padded = torch.cat([h, pad_block], dim=0)
            # pad labels
            lbl_padded = lbls + [-100] * pad_len
            # pad mask
            mask = [True] * T + [False] * pad_len
        else:
            h_padded = h
            lbl_padded = lbls
            mask = [True] * T

        batch_hidden.append(h_padded)
        batch_labels.append(lbl_padded)
        batch_masks.append(mask)

    # stack now that they are equal-sized
    hidden = torch.stack(batch_hidden, dim=0)  # [B, L, H]
    labels = torch.tensor(batch_labels, device=device)  # [B, L]
    mask = torch.tensor(batch_masks, device=device)

    return hidden, labels, mask, result


def debug_print_chunk(
    words: List[str],
    word_ids: List[Optional[int]],
    gold: List[int],
    pred: List[int],
    label_list: List[str],
):
    """
    Pretty-print a full word/alignment/prediction table for one sample.

    words     - list of word tokens (original input)
    token_ids - for visual clarity, not required (can be None)
    word_ids  - mapping from tokenizer token -> word index
    gold      - gold labels for each **token**
    pred      - predicted labels for each **token**
    label_list - list of label strings
    """
    return
    print("\n====== DEBUG CHUNK ======")

    # Build per-token lines
    rows = []
    seq_len = min(len(word_ids), len(pred), len(gold))
    print(f"[DEBUG] seq_len={seq_len}, word_ids={len(word_ids)}, gold={len(gold)}, pred={len(pred)}")

    for tok_idx in range(seq_len):
        widx = word_ids[tok_idx]
        if widx is None:
            continue
        tok_word = words[widx] if widx is not None else "<SUBWORD>"
        gold_idx = gold[tok_idx]
        pred_idx = pred[tok_idx]

        gold_str = label_list[gold_idx] if gold_idx != -100 else "PAD"
        pred_str = label_list[pred_idx]

        mark = "" if gold_idx == pred_idx else " <-- MISMATCH"

        rows.append((tok_idx, tok_word, gold_str, pred_str, mark))

    # Print formatted table
    print(f"{'tok':<4} {'WORD':<15} {'GOLD':<12} {'PRED':<12} {'NOTE'}")
    print("-" * 60)

    for (tok, w, g, p, mark) in rows:
        print(f"{tok:<4} {w:<15} {g:<12} {p:<12} {mark}")

    print("=" * 60)


def _train_one_epoch(
    dataloader: DataLoader,
    task_type: TaskType,
    device: str,
    head: TaskHead,
    optimizer: torch.optim.Optimizer,
    scheduler,
):
    total_loss = 0
    for batch in tqdm(dataloader, desc="  Training"):
        hidden, labels, mask, result = _get_input_and_labels(task_type=task_type,
                                                             batch=batch,
                                                             num_attention_heads=head.num_attention_heads,
                                                             device=device)

        _, loss = head(hidden, labels=labels, mask=mask)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(head.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss


def _evaluate_one_epoch(
    dataloader: DataLoader,
    task_type: TaskType,
    device: str,
    head: TaskHead,
):
    """Performs one evaluation epoch (no gradient updates)."""
    head.eval()
    total_loss = 0
    y_true_all = []
    y_pred_all = []

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Validation"):
            hidden, labels, mask, result = _get_input_and_labels(task_type=task_type,
                                                                 batch=batch,
                                                                 num_attention_heads=head.num_attention_heads,
                                                                 device=device)

            if task_type == TaskType.TOKEN:
                logits, loss = head(hidden, labels=labels, mask=mask)
            else:
                logits, loss = head(hidden, labels=labels)
                y_true = labels.cpu().numpy()
                y_true_all.append(y_true)
                if task_type == TaskType.SENTENCE:
                    y_pred = torch.argmax(logits, dim=-1).cpu().numpy()
                elif task_type == TaskType.SENTENCE_MULTILABEL:
                    y_pred = (torch.sigmoid(logits) > 0.5).int().cpu().numpy()
                else:
                    y_pred = np.array([])  #
                y_pred_all.append(y_pred)

            total_loss += loss.item()

    macro_f1 = None
    if task_type.is_sentence_level():
        y_true_all = np.concatenate(y_true_all, axis=0)
        y_pred_all = np.concatenate(y_pred_all, axis=0)
        macro_f1 = f1_score(y_true_all, y_pred_all, average='macro')

    return total_loss, macro_f1


def train_task(
    task_name,
    annotation_type,
    dataset,
    label2id,
    task_type: TaskType,
    batch_size=32,
    num_epochs=100,
    lr=2e-4,
    dropout=0.2,
    warmup_ratio=0.1,
    use_mixup=False,
    alpha=16,
    rank=16,
    lstm_hidden: Optional[int] = None,
    language: Optional[str] = None,
    min_confidence: float = 0,
    default_class: Optional[str] = None,
    ignore_classes: Optional[List[str]] = None,
    validation_split_ratio=0.1,
    patience=5,
    use_focal_loss=False,
    num_attention_heads=0,
    device=config.TRAINING_DEVICE,
):
    params = {
        "Task Name": task_name,
        "Annotation Type": annotation_type,
        "Language": language or "auto",
        "Task Type": task_type,
        "Batch Size": batch_size,
        "Num Epochs": num_epochs,
        "Learning Rate": lr,
        "Dropout": dropout,
        "Warmup Ratio": warmup_ratio,
        "Use Mixup": use_mixup,
        "Adapter Alpha": alpha,
        "Adapter Rank": rank,
        "LSTM Hidden": lstm_hidden,
        "Min Confidence": min_confidence,
        "Default Class": default_class,
        "Ignore Classes": ", ".join(ignore_classes) if ignore_classes else "None",
        "Validation Split": validation_split_ratio,
        "Early Stop Patience": patience,
        "Use Focal Loss": use_focal_loss,
        "Attention Heads": num_attention_heads,
        "Num Labels": len(label2id),
        "Labels": ", ".join(list(label2id.keys())),
    }

    print(f"\n🚀 Training new task: {task_name} ({task_type})")
    print("\n" + "=" * 60)
    print("               TRAINING CONFIGURATION")
    print("=" * 60)

    # Pretty key-value alignment
    max_key_len = max(len(k) for k in params.keys())
    for key, value in params.items():
        print(f"{key:<{max_key_len}} : {value}")

    print("=" * 60 + "\n")

    if task_type.is_sentence_level():
        total_size = len(dataset)
        labels_to_stratify = _get_labels_for_split(dataset, task_type, total_size)
        all_indices = np.arange(total_size)

        # Use train_test_split for simple, clean stratification
        train_indices, val_indices = train_test_split(
            all_indices,
            test_size=validation_split_ratio,
            random_state=42,
            stratify=labels_to_stratify
        )
        train_indices = train_indices.tolist()
        val_indices = val_indices.tolist()
        train_size = len(train_indices)
        val_size = len(val_indices)
        train_dataset = Subset(dataset, train_indices)
        val_dataset = Subset(dataset, val_indices)

    else:
        val_size = int(len(dataset) * validation_split_ratio)
        train_size = len(dataset) - val_size
        train_dataset, val_dataset = random_split(
            dataset, [train_size, val_size]
        )

    print(f"Dataset split: Training ({train_size}), Validation ({val_size})")

    if task_type == TaskType.SENTENCE_MULTILABEL:
        label_matrix = np.stack([d["label"] for d in train_dataset])
        positive_counts = np.sum(label_matrix, axis=0)
        N = len(train_dataset)
        alpha_np = (N - positive_counts) / np.clip(positive_counts, a_min=1, a_max=None)
        weights = torch.tensor(alpha_np, dtype=torch.float32)
        weights = weights.to(device)
    elif task_type == TaskType.SENTENCE:
        labels = np.array([train_dataset[i]["label"] for i in range(len(train_dataset))])
        counts = np.bincount(labels)
        weights = torch.tensor(1.0 / np.maximum(counts, 1), dtype=torch.float32)
        weights = weights / weights.mean()
        weights = weights.to(device)
    else:
        weights = None

    if task_type.is_sentence_level():
        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_dataloader = DataLoader(val_dataset, batch_size=batch_size * 2, shuffle=False)
    else:
        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=False,
                                      collate_fn=token_classification_collate)
        val_dataloader = DataLoader(val_dataset, batch_size=batch_size * 2, shuffle=False,
                                    collate_fn=token_classification_collate)

    path = f"{config.ADAPTERS_DIR}/{task_name}"
    os.makedirs(path, exist_ok=True)

    num_labels = len(label2id)
    transfer_layer = nn.Linear(embedder.dimensions, embedder.dimensions)
    label_list = [""] * num_labels
    for label, idx in label2id.items():
        label_list[idx] = label

    head = TaskHead(
        hidden_size=embedder.dimensions,
        num_labels=num_labels,
        task_type=task_type,
        original_layer=transfer_layer,
        dropout=dropout,
        use_mixup=use_mixup,
        lstm_hidden=lstm_hidden,
        alpha=alpha,
        rank=rank,
        weights=weights,
        use_focal_loss=use_focal_loss,
        num_attention_heads=num_attention_heads,
        label_list=label_list,
    ).to(device)

    optimizer = torch.optim.AdamW(list(head.parameters()), lr=lr)
    num_training_steps = len(train_dataloader) * num_epochs
    num_warmup_steps = int(num_training_steps * warmup_ratio)

    if task_type.is_sentence_level():
        scheduler = get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=num_training_steps
        )
    else:
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=num_training_steps,
        )

    best_val_loss = float("inf")
    best_val_f1 = -1.0
    patience_counter = 0
    best_model = None
    id2label = {v: k for k, v in label2id.items()}

    for epoch in range(num_epochs):
        head.train()

        print(f"Epoch {epoch + 1}/{num_epochs}: lr={optimizer.param_groups[0]['lr']}")
        total_loss = _train_one_epoch(
            dataloader=train_dataloader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=device,
            head=head,
            task_type=task_type,
        )
        avg_train_loss = total_loss / len(train_dataloader)

        val_loss, val_f1 = _evaluate_one_epoch(
            dataloader=val_dataloader,
            device=device,
            head=head,
            task_type=task_type,
        )
        avg_val_loss = val_loss / len(val_dataloader)
        print(
            f"Epoch {epoch + 1} avg training loss: {avg_train_loss:.4f} avg validation loss: {avg_val_loss:.4f} {f' | Validation F1 (macro): {val_f1:.4f}' if val_f1 is not None else ''}"
        )

        if val_f1 is not None and val_f1 > best_val_f1:
            print(f"Validation F1 improved ({best_val_f1:.4f} -> {val_f1:.4f}). Saving best model...")
            best_val_f1 = val_f1
            patience_counter = 0
            best_model = head.state_dict()

        elif val_f1 is not None:
            patience_counter += 1
            print(f"Validation F1 did not improve. Patience: {patience_counter}/{patience}")

        elif avg_val_loss < best_val_loss:
            print(f"Validation loss improved ({best_val_loss:.4f} -> {avg_val_loss:.4f}). Saving best model...")
            best_val_loss = avg_val_loss
            patience_counter = 0
            best_model = head.state_dict()
        else:
            patience_counter += 1
            print(f"Validation loss did not improve. Patience: {patience_counter}/{patience}")

        if patience_counter >= patience:
            print(f"🛑 Early stopping triggered after {patience_counter} epochs without improvement.")
            break

        if task_type == TaskType.TOKEN:
            data = val_dataset[[0, 1, 2, 3]]
            text = data["text"]
            hidden, labels, mask, result = _get_input_and_labels(task_type, data, 0, device)
            outputs = head(hidden)
            print(outputs)

        # print()

    # Save results
    print(f"💾 Saving adapter and head for task '{task_name}'")
    torch.save(best_model, f"{path}/{task_name}_head.pt")

    transformer = MultiTaskTransformer()
    adapter = transformer.registry.register_task(Task(
        name=task_name,
        type=task_type,
        label2id=label2id,
        annotation_type=annotation_type,
        language=language,
        min_confidence=min_confidence,
        default_class=default_class,
        ignore_classes=ignore_classes or [],
        alpha=alpha,
        rank=rank,
        num_attention_heads=num_attention_heads,
        lstm_hidden=lstm_hidden,
    ))

    with open(f"{path}/{task_name}.config.json", "w") as fp:
        json.dump(adapter.to_json(), fp, indent=2)

    adapter.head = head
    print(f"✅ Task '{task_name}' trained and registered.")
