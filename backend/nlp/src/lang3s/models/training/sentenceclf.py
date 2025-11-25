import os
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from torch.utils.data.dataset import Dataset, Subset
from tqdm import tqdm
from transformers import get_cosine_schedule_with_warmup  # pyright: ignore[reportPrivateImportUsage]

from lang3s import config
from lang3s.models.transformer.heads import SentenceClassificationHead
from lang3s.models.transformer.task import SentenceClassificationParams, Task, TaskType
from .trainer import Trainer


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


class SentenceClassifierTrainer(Trainer):

    def __init__(self, task_type: TaskType, warmup_ratio=0.1, **kwargs):
        super().__init__(**kwargs)
        self.best_model = None
        self.task_type = task_type
        self.validation_split = kwargs.get("validation_split", 0.1)
        self.clf_params = SentenceClassificationParams(**kwargs)
        self.warmup_ratio = warmup_ratio
        self.params["warmup_ratio"] = self.warmup_ratio
        self.best_val_loss = float("inf")
        self.best_val_f1 = -1.0
        self.task = Task(
            name=self.name,
            annotation_type=self.annotation_type,
            type=kwargs.get("task_type", TaskType.SENTENCE),
            language=self.lang,
            label2id=self.dataset.label2idx,  # type: ignore
            params=self.clf_params
        )
        self.clf = None

    def train(self):
        self._print_train_information(name=self.task.name, annotation_type=self.task.annotation_type)
        total_size = len(self.dataset)
        labels_to_stratify = _get_labels_for_split(self.dataset, self.task_type, total_size)
        all_indices = np.arange(total_size)
        train_indices, val_indices = train_test_split(
            all_indices,
            test_size=self.validation_split,
            random_state=42,
            stratify=labels_to_stratify
        )
        train_indices = train_indices.tolist()
        val_indices = val_indices.tolist()
        train_size = len(train_indices)
        val_size = len(val_indices)
        train_dataset = Subset(self.dataset, train_indices)
        val_dataset = Subset(self.dataset, val_indices)

        weights = None
        if self.task_type == TaskType.SENTENCE_MULTILABEL:
            label_matrix = np.stack([d["label"] for d in train_dataset])
            positive_counts = np.sum(label_matrix, axis=0)
            N = len(train_dataset)
            alpha_np = (N - positive_counts) / np.clip(positive_counts, a_min=1, a_max=None)
            weights = torch.tensor(alpha_np, dtype=torch.float32)
            weights = weights.to(self.device)
        elif self.task_type == TaskType.SENTENCE:
            labels = np.array([train_dataset[i]["label"] for i in range(len(train_dataset))])
            counts = np.bincount(labels)
            weights = torch.tensor(1.0 / np.maximum(counts, 1), dtype=torch.float32)
            weights = weights / weights.mean()
            weights = weights.to(self.device)

        train_dataloader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)
        val_dataloader = DataLoader(val_dataset, batch_size=self.batch_size * 2, shuffle=False)
        path = f"{config.ADAPTERS_DIR}/{self.name}"
        os.makedirs(path, exist_ok=True)

        dummy_layer = nn.Linear(self.embedding_dim, self.embedding_dim)
        self.clf = SentenceClassificationHead(
            hidden_size=self.embedding_dim,
            num_labels=len(self.dataset.label2idx),
            task_type=self.task_type,
            original_layer=dummy_layer,
            rank=self.clf_params.rank,
            alpha=self.clf_params.alpha,
            num_attention_heads=self.clf_params.num_attention_heads,
            use_dora=self.clf_params.use_dora,
            use_mixup=self.clf_params.use_mixup,
            use_focal_loss=self.clf_params.use_focal_loss,
            weights=weights,
            mixup_alpha=self.clf_params.mixup_alpha,
        )
        self.clf.to(self.device)
        self.embedder.device = self.device

        optimizer = torch.optim.AdamW(list(self.clf.parameters()), lr=self.lr)
        num_training_steps = len(train_dataloader) * self.num_epochs
        num_warmup_steps = int(num_training_steps * self.warmup_ratio)
        scheduler = get_cosine_schedule_with_warmup(
            optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=num_training_steps
        )
        self.best_val_loss = float("inf")
        self.best_val_f1 = -1.0
        self.patience_counter = 0
        self.best_model = None

        for epoch in range(self.num_epochs):
            print(f"Epoch {epoch + 1}/{self.num_epochs}")
            total_loss = self.train_one_epoch(
                epoch=epoch,
                dataloader=train_dataloader,
                optimizer=optimizer,
                scheduler=scheduler,
            )
            avg_train_loss = total_loss / len(train_dataloader)

            val_loss, val_f1 = self.eval_one_epoch(
                dataloader=val_dataloader,
                epoch=epoch,
            )
            avg_val_loss = val_loss / len(val_dataloader)
            print(
                f"Epoch {epoch + 1} avg training loss: {avg_train_loss:.4f} avg validation loss: {avg_val_loss:.4f} {f' | Validation F1 (macro): {val_f1:.4f}' if val_f1 is not None else ''}"
            )

            if val_f1 is not None and val_f1 > self.best_val_f1:
                print(f"Validation F1 improved ({self.best_val_f1:.4f} -> {val_f1:.4f}). Saving best model...")
                self.best_val_f1 = val_f1
                self.patience_counter = 0
                self.best_model = self.clf.state_dict()

            else:
                self.patience_counter += 1
                print(f"Validation F1 did not improve. Patience: {self.patience_counter}/{self.patience}")

            if self.patience_counter >= self.patience:
                print(f"🛑 Early stopping triggered after {self.patience_counter} epochs without improvement.")
                break

            print()

        self.save_model(self.task)

    def eval_one_epoch(self,
                       dataloader: DataLoader,
                       epoch: int):
        if self.clf is None:
            raise Exception("No model has been defined.")

        self.clf.eval()
        total_loss = 0
        y_true_all = []
        y_pred_all = []
        for batch in tqdm(dataloader, desc="Evaluating"):
            hidden, labels, mask = self._prepare_batch(batch=batch)
            logits, loss = self.clf(hidden, labels=labels, mask=mask)
            y_true = labels.cpu().numpy()
            y_true_all.append(y_true)
            if self.task_type == TaskType.SENTENCE:
                y_pred = torch.argmax(logits, dim=-1).cpu().numpy()
            else:
                y_pred = (torch.sigmoid(logits) > 0.5).int().cpu().numpy()
            y_pred_all.append(y_pred)

            total_loss += loss.item()

        y_true_all = np.concatenate(y_true_all, axis=0)
        y_pred_all = np.concatenate(y_pred_all, axis=0)
        macro_f1 = f1_score(y_true_all, y_pred_all, average='macro')

        return total_loss, macro_f1

    def _prepare_batch(
        self,
        batch: Dict[str, Any],
    ):
        raw_texts = batch["text"]
        raw_labels = batch["label"]  # for token tasks: list[list[int]]
        result = self.embedder(
            raw_texts,
        )
        mask = None
        if self.clf_params.num_attention_heads > 0:
            hidden, mask = result.padded_token_embeddings_with_mask()
            hidden = torch.from_numpy(hidden).type(torch.float32, non_blocking=True).to(self.device)
            mask = torch.from_numpy(mask).type(torch.bool, non_blocking=True).to(self.device)
        else:
            hidden = torch.stack(
                [torch.as_tensor(e, device=self.device, dtype=torch.float32) for e in result.sentence_embeddings],
                dim=0,
            ).to(self.device)

        if isinstance(raw_labels, torch.Tensor):
            labels = raw_labels.type(torch.long).to(self.device)
        else:
            labels = torch.tensor(raw_labels, device=self.device)

        return hidden, labels, mask

    def train_one_epoch(self,
                        dataloader: DataLoader,
                        epoch: int,
                        optimizer: torch.optim.Optimizer,
                        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None):
        if self.clf is None:
            raise Exception("No model has been defined.")

        self.clf.train()
        total_loss = 0
        for batch in tqdm(dataloader, desc="  Training"):
            hidden, labels, mask = self._prepare_batch(batch=batch)

            _, loss = self.clf(hidden, labels=labels, mask=mask)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.clf.parameters(), max_norm=1.0)  # type Ignore
            optimizer.step()
            if scheduler is not None:
                scheduler.step()

            total_loss += loss.item()

        return total_loss
