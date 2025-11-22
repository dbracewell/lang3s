import json
import os
from typing import List, Optional

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

from lang3s import config
from lang3s.models.embedder import Embedder
from lang3s.models.transformer import MultiTaskTransformer
from .helpers import align_labels
from .shared_types import TaskType
from .task_registry import Task, TaskHead


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
                # Multiclass: label is a single integer. Use item() for primitives.
                all_labels.append(label.item() if isinstance(label, torch.Tensor) else label)

            elif task_type == TaskType.SENTENCE_MULTILABEL:
                # Multilabel: label is a list/tensor of 0s and 1s. Stratify by the unique combination.
                # Use frozenset of the tuple representation for a hashable key.
                label_tuple = tuple(label.tolist() if isinstance(label, torch.Tensor) else label)
                all_labels.append(frozenset(label_tuple))

            else:
                # Fallback for unexpected label structure
                all_labels.append(None)
        except Exception:
            all_labels.append(None)  # Cannot stratify this sample

    return all_labels


def _train_one_epoch(
    dataloader: DataLoader,
    task_type: TaskType,
    device: str,
    head: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler,
):
    embedder = Embedder()
    total_loss = 0
    for batch in tqdm(dataloader, desc="  Training"):
        texts = batch["text"]
        labels = batch["label"]

        if task_type == TaskType.TOKEN:
            texts = [[t for t in s if t != "~~~EMPTY~~~"] for s in texts]

        result = embedder(
            texts, is_split_into_words=task_type == TaskType.TOKEN
        )

        if task_type.is_sentence_level():
            labels = labels.to(device)
            mask = None
        else:
            labels = [[t for t in s if t != -500] for s in labels]
            aligned = []
            for sentence_labels, mapping in zip(labels, result.mapping):
                aligned.append(
                    torch.tensor(
                        align_labels(mapping, sentence_labels),
                        dtype=torch.int64,
                    )
                )
            labels = pad_sequence(
                aligned, batch_first=True, padding_value=-100
            ).to(device)
            mask = labels != -100

        hidden = pad_sequence(
            [torch.Tensor(e) for e in result.token_embeddings],
            batch_first=True,
            padding_value=0,
        ).to(device)

        if task_type == TaskType.TOKEN:
            _, loss = head(hidden, labels=labels, mask=mask)
        else:
            _, loss = head(hidden, labels=labels)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(head.parameters(), max_norm=1.0)
        scheduler.step()
        optimizer.step()

        total_loss += loss.item()

    return total_loss


def _evaluate_one_epoch(
    dataloader: DataLoader,
    task_type: TaskType,
    device: str,
    head: torch.nn.Module,
):
    """Performs one evaluation epoch (no gradient updates)."""
    head.eval()
    total_loss = 0
    y_true_all = []
    y_pred_all = []

    embedder = Embedder()
    with torch.no_grad():
        for batch in tqdm(dataloader, desc="Validation"):
            texts = batch["text"]
            labels = batch["label"]

            if task_type == TaskType.TOKEN:
                texts = [[t for t in s if t != "~~~EMPTY~~~"] for s in texts]

            # Use the passed embedder instance
            result = embedder(
                texts, is_split_into_words=task_type == TaskType.TOKEN
            )

            if task_type.is_sentence_level():
                labels = labels.to(device)
                mask = None
            else:
                labels = [[t for t in s if t != -500] for s in labels]
                aligned = []
                for sentence_labels, mapping in zip(labels, result.mapping):
                    aligned.append(
                        torch.tensor(
                            align_labels(mapping, sentence_labels),
                            dtype=torch.int64,
                        )
                    )
                labels = pad_sequence(
                    aligned, batch_first=True, padding_value=-100
                ).to(device)
                mask = labels != -100

            hidden = pad_sequence(
                [torch.Tensor(e) for e in result.token_embeddings],
                batch_first=True,
                padding_value=0,
            ).to(device)

            if task_type == TaskType.TOKEN:
                _, loss = head(hidden, labels=labels, mask=mask)
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
        # Concatenate all true/pred arrays
        y_true_all = np.concatenate(y_true_all, axis=0)
        y_pred_all = np.concatenate(y_pred_all, axis=0)

        # Use macro F1 as a general robust metric for multiclass/multilabel
        macro_f1 = f1_score(y_true_all, y_pred_all, average='macro')

    return total_loss, macro_f1


def train_task(
    task_name,
    annotation_type,
    dataset,
    label2id,
    task_type: TaskType,
    batch_size=32,
    num_epochs=10,
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
):
    transformer = MultiTaskTransformer()
    embedder = Embedder()

    print(f"\n🚀 Training new task: {task_name} ({task_type})")

    if task_type.is_sentence_level():
        print("Performing stratified split for sentence-level task...")

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
        alpha_np = (N - positive_counts) / N
        weights = torch.tensor(alpha_np, dtype=torch.float32)
        weights = weights.to(transformer.device)
    elif task_type == TaskType.SENTENCE:
        labels = np.array([train_dataset[i]["label"] for i in range(len(train_dataset))])
        counts = np.bincount(labels)
        weights = torch.tensor(1.0 / np.maximum(counts, 1), dtype=torch.float32)
        weights = weights / weights.mean()
        weights = weights.to(transformer.device)
    else:
        weights = None

    train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_dataloader = DataLoader(val_dataset, batch_size=batch_size * 2, shuffle=False)

    path = f"{config.ADAPTERS_DIR}/{task_name}"
    os.makedirs(path, exist_ok=True)

    num_labels = len(label2id)
    original_linear_layer = nn.Linear(embedder.dimensions, embedder.dimensions)
    head = TaskHead(
        hidden_size=embedder.dimensions,
        num_labels=num_labels,
        task_type=task_type,
        original_layer=original_linear_layer,
        dropout=dropout,
        use_mixup=use_mixup,
        lstm_hidden=lstm_hidden,
        alpha=alpha,
        rank=rank,
        weights=weights,
        use_focal_loss=use_focal_loss,
    ).to(transformer.device)

    optimizer = torch.optim.AdamW(list(head.parameters()), lr=lr)
    num_training_steps = len(train_dataloader) * num_epochs
    num_warmup_steps = int(num_training_steps * warmup_ratio)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=num_warmup_steps,
        num_training_steps=num_training_steps
    )

    best_val_loss = float("inf")
    best_val_f1 = -1.0
    patience_counter = 0
    best_model = None

    head.train()
    for epoch in range(num_epochs):
        print(f"Epoch {epoch + 1}/{num_epochs}: lr={optimizer.param_groups[0]['lr']}")
        total_loss = _train_one_epoch(
            dataloader=train_dataloader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=transformer.device,
            head=head,
            task_type=task_type,
        )
        avg_train_loss = total_loss / len(train_dataloader)

        val_loss, val_f1 = _evaluate_one_epoch(
            dataloader=val_dataloader,
            device=transformer.device,
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

        print()

    # Save results
    print(f"💾 Saving adapter and head for task '{task_name}'")
    torch.save(best_model, f"{path}/{task_name}_head.pt")

    adapter = transformer.registry.register_task(Task(
        name=task_name,
        type=task_type,
        label2id=label2id,
        annotation_type=annotation_type,
        language=language,
        min_confidence=min_confidence,
        default_class=default_class,
        ignore_classes=ignore_classes,
        alpha=alpha,
        rank=rank,
    ))
    with open(f"{path}/{task_name}.config.json", "w") as fp:
        json.dump(adapter.to_json(), fp, indent=2)

    adapter.head = head
    print(f"✅ Task '{task_name}' trained and registered.")
