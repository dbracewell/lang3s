import sys
from typing import Any, Dict, List, Optional

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from torch.utils.data.dataset import Dataset, Subset
from tqdm import tqdm
from transformers import (
    get_cosine_schedule_with_warmup,
    get_linear_schedule_with_warmup,
)

from lang3s.core import config
from lang3s.nlp.models.task_transformer.heads import SentenceClassificationHead
from lang3s.nlp.models.task_transformer.task import (
    SentenceClassificationParams,
    TaskType,
)

from .trainer import Trainer, logger


def _get_labels_for_split(
    dataset: Dataset, task_type: TaskType, total_size: int
) -> List:
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
                all_labels.append(
                    label.item() if isinstance(label, torch.Tensor) else label
                )

            elif task_type == TaskType.SENTENCE_MULTILABEL:
                label_tuple = tuple(
                    label.tolist() if isinstance(label, torch.Tensor) else label
                )
                all_labels.append(label_tuple)

            else:
                all_labels.append(None)
        except Exception:
            all_labels.append(None)  # Cannot stratify this sample

    return all_labels


class SentenceClassifierTrainer(Trainer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scheduler_name = kwargs.get("scheduler_name", "cosine")
        self.warmup_ratio = kwargs.get("warmup_ratio", 0.15)

    def _create_clf_params(self, **kwargs):
        clf_params = SentenceClassificationParams(
            **self.params,
        )
        if clf_params.use_attention and clf_params.num_attention_heads > 0:
            self.embedding_dim = config.TOKEN_EMBEDDING_DIMENSION
        else:
            clf_params.num_attention_heads = 0
            self.params["num_attention_heads"] = 0
            self.embedding_dim = config.SEMANTIC_EMBEDDING_DIMENSION
        return clf_params

    def _create_clf(self) -> torch.nn.Module:
        return SentenceClassificationHead(
            hidden_size=self.embedding_dim,
            num_labels=self.num_labels,
            task_type=self.task_type,
            weights=self.weights,
            **self.clf_params.model_dump(),
        )

    def _train_impl(self):
        self.task.input_type = (
            "token"
            if self.clf_params.use_attention and self.clf_params.num_attention_heads > 0
            else "sentence"
        )
        optimizer = torch.optim.AdamW(
            list(self.clf.parameters()), lr=self.lr, weight_decay=0.01
        )
        num_training_steps = len(self.train_dataloader) * self.num_epochs
        num_warmup_steps = int(num_training_steps * self.warmup_ratio)
        if self.scheduler_name == "linear":
            scheduler = get_linear_schedule_with_warmup(
                optimizer,
                num_warmup_steps=num_warmup_steps,
                num_training_steps=num_training_steps,
            )
        else:
            scheduler = get_cosine_schedule_with_warmup(
                optimizer,
                num_warmup_steps=num_warmup_steps,
                num_training_steps=num_training_steps,
            )
        best_val_f1 = -1.0
        patience_counter = 0
        self.best_model = None

        epoch = 0
        for epoch in range(self.num_epochs):
            logger.info(f"Epoch {epoch + 1}/{self.num_epochs}")
            self.train_one_epoch(
                optimizer=optimizer,
                scheduler=scheduler,
            )
            metrics = self.eval_one_epoch()
            if not self.is_trial:
                self.print_metrics(metrics, epoch=epoch)

            macro_f1 = metrics["macro_f1"]
            if macro_f1 > best_val_f1:
                logger.info(
                    f"Validation F1 improved ({best_val_f1:.4f} -> {macro_f1:.4f}). "
                    "Saving best model..."
                )
                best_val_f1 = macro_f1
                patience_counter = 0
                self.best_model = {
                    k: v.detach().cpu().clone()
                    for k, v in self.clf.state_dict().items()
                }
            else:
                patience_counter += 1
                logger.info(
                    f"Validation F1 did not improve. "
                    f"Patience: {patience_counter}/{self.patience}"
                )

            if patience_counter >= self.patience:
                logger.info(
                    f"🛑 Early stopping triggered after {patience_counter} epochs "
                    "without improvement."
                )
                break

        return epoch

    def print_metrics(self, metrics: Dict[str, Any], epoch=-1, file=sys.stdout):
        loss = metrics["loss"]
        macro_f1 = metrics["macro_f1"]
        micro_p = metrics["micro_p"]
        micro_r = metrics["micro_r"]
        micro_f1 = metrics["micro_f1"]
        macro_p = metrics["macro_p"]
        macro_r = metrics["macro_r"]
        class_p = metrics["class_p"]
        class_r = metrics["class_r"]
        class_f1 = metrics["class_f1"]
        support = metrics["support"]

        if epoch >= 0:
            print(f"\n===== EPOCH {epoch + 1} RESULTS =====", file=file)
        else:
            print("\n===== FINAL TEST RESULTS =====", file=file)

        print(f"    Loss: {loss:.4f}", file=file)
        print("---------------------------", file=file)
        print(f" Micro P: {micro_p:.4f}", file=file)
        print(f" Micro R: {micro_r:.4f}", file=file)
        print(f"Micro F1: {micro_f1:.4f}", file=file)
        print("---------------------------", file=file)
        print(f" Macro P: {macro_p:.4f}", file=file)
        print(f" Macro R: {macro_r:.4f}", file=file)
        print(f"Macro F1: {macro_f1:.4f}", file=file)

        print("\n===== PER-CLASS METRICS =====", file=file)
        max_len = max(len(lbl) for lbl in self.label2idx.keys())

        for c in range(self.num_labels):
            print(
                f"Class {c:<4} {self.idx2label[c]:<{max_len}}: "
                f"P={class_p[c]:.4f}, R={class_r[c]:.4f}, F1={class_f1[c]:.4f}, "
                f"support={support[c]}",
                file=file,
            )

    def eval_one_epoch(self) -> Dict[str, Any]:
        if self.clf is None:
            raise Exception("No model has been defined.")

        self.clf.eval()
        total_loss = 0
        y_true_all = []
        y_pred_all = []
        all_logits = []

        for batch in tqdm(self.val_dataloader, desc="Evaluating"):
            hidden, labels, mask = self._prepare_batch(batch=batch)
            with torch.no_grad():
                logits, loss = self.clf(hidden, labels=labels, mask=mask)

            all_logits.append(logits.cpu().numpy())
            y_true_all.append(labels.cpu().numpy())

            if self.task_type == TaskType.SENTENCE:
                y_pred = torch.argmax(logits, dim=-1).cpu().numpy()
            else:
                y_pred = (torch.sigmoid(logits) > 0.5).int().cpu().numpy()

            y_pred_all.append(y_pred)

            total_loss += loss.item()

        y_true_all = np.concatenate(y_true_all, axis=0)
        y_pred_all = np.concatenate(y_pred_all, axis=0)
        class_p, class_r, class_f1, support = precision_recall_fscore_support(
            y_true_all,
            y_pred_all,
            labels=list(range(len(self.label2idx))),
            zero_division=0,
        )
        macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
            y_true_all, y_pred_all, average="macro", zero_division=0
        )
        micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(
            y_true_all, y_pred_all, average="micro", zero_division=0
        )
        avg_val_loss = total_loss / len(self.val_dataloader)

        return {
            "loss": avg_val_loss,
            "macro_p": macro_p,
            "macro_r": macro_r,
            "macro_f1": macro_f1,
            "micro_p": micro_p,
            "micro_r": micro_r,
            "micro_f1": micro_f1,
            "class_p": class_p,
            "class_r": class_r,
            "class_f1": class_f1,
            "support": support,
        }

    def prepare_data(self):
        if self.val_dataset is None:
            total_size = len(self.train_dataset)
            labels_to_stratify = _get_labels_for_split(
                self.train_dataset, self.task_type, total_size
            )
            all_indices = np.arange(total_size)
            train_indices, val_indices = train_test_split(
                all_indices,
                test_size=self.validation_split,
                random_state=42,
                stratify=labels_to_stratify,
            )
            train_indices = train_indices.tolist()
            val_indices = val_indices.tolist()
            self.train_dataset = Subset(self.train_dataset, train_indices)
            self.val_dataset = Subset(self.train_dataset.dataset, val_indices)

        if self.task_type == TaskType.SENTENCE_MULTILABEL:
            label_matrix = np.stack([d["label"] for d in self.train_dataset])
            positive_counts = np.sum(label_matrix, axis=0)
            N = len(self.train_dataset)
            alpha_np = (N - positive_counts) / np.clip(
                positive_counts, a_min=1, a_max=None
            )
            weights = torch.tensor(alpha_np, dtype=torch.float32)
            self.weights = weights.to(self.device)
        elif self.task_type == TaskType.SENTENCE:
            labels = np.array(
                [self.train_dataset[i]["label"] for i in range(len(self.train_dataset))]
            )
            counts = np.bincount(labels)
            weights = torch.tensor(1.0 / np.maximum(counts, 1), dtype=torch.float32)
            weights = weights / weights.mean()
            self.weights = weights.to(self.device)

        self.train_dataloader = DataLoader(
            self.train_dataset, batch_size=self.batch_size, shuffle=True
        )
        self.val_dataloader = DataLoader(
            self.val_dataset, batch_size=self.batch_size, shuffle=False
        )

    def _prepare_batch(
        self,
        batch: Dict[str, Any],
    ):
        raw_texts = batch["text"]
        raw_labels = batch["label"]
        result = self.embedder(raw_texts)
        mask = None
        if self.clf_params.use_attention and self.clf_params.num_attention_heads > 0:
            hidden, mask = result.padded_token_embeddings_with_mask()
            hidden = torch.from_numpy(hidden).type(torch.float32).to(self.device)
            mask = torch.from_numpy(mask).type(torch.bool).to(self.device)
        else:
            hidden = torch.stack(
                [
                    torch.as_tensor(e, device=self.device, dtype=torch.float32)
                    for e in result.sentence_embeddings
                ],
                dim=0,
            ).to(self.device)

        if isinstance(raw_labels, torch.Tensor):
            labels = raw_labels.type(torch.long).to(self.device)
        else:
            labels = torch.tensor(raw_labels, device=self.device)

        return hidden, labels, mask

    def train_one_epoch(
        self,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    ):
        if self.clf is None:
            raise Exception("No model has been defined.")

        self.clf.train()
        total_loss = 0
        for batch in tqdm(self.train_dataloader, desc="  Training"):
            hidden, labels, mask = self._prepare_batch(batch=batch)
            _, loss = self.clf(hidden, labels=labels, mask=mask)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                self.clf.parameters(), max_norm=1.0
            )  # type Ignore
            optimizer.step()
            if scheduler is not None:
                scheduler.step()

            total_loss += loss.item()

        return total_loss
