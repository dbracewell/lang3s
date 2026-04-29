import itertools
import sys
from typing import Any, Counter, Dict, List, Optional, Tuple

import seqeval.metrics
import torch
from sklearn.metrics import precision_recall_fscore_support
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm
from transformers import (
    get_cosine_schedule_with_warmup,
    get_linear_schedule_with_warmup,
)

from lang3s.models.transformer.heads import TokenClassificationHead
from lang3s.models.transformer.shared_types import TaskType
from lang3s.models.transformer.task import TokenClassificationParams, repair_bio_seq
from lang3s.utils import flatten

from .trainer import Lang3sDataset, Trainer, logger


def token_classification_collate(batch):
    texts = [sample["text"] for sample in batch]
    labels = [sample["label"] for sample in batch]
    return {
        "text": texts,
        "label": labels,
    }


class TokenDataset(Lang3sDataset):

    def __init__(self, sentences: List[Tuple[List[str], List[str]]]):
        super().__init__()
        self.sentences: List[Tuple[List[str], List[str]]] = sentences
        all_labels = set()
        for sentence in self.sentences:
            for label in sentence[1]:
                all_labels.add(label)
        all_labels = sorted(all_labels)
        if "O" in all_labels:
            all_labels.remove("O")
            all_labels = ["O"] + all_labels
        all_b = [tag[2:] for tag in all_labels if tag.startswith("B")]
        for tag in all_b:
            i_tag = f"I-{tag}"
            if i_tag not in all_labels:
                all_labels.append(i_tag)

        self.label2idx = {lbl: idx for idx, lbl in enumerate(all_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

    def __len__(self):
        return len(self.sentences)

    def __getitem__(self, idx: int):
        tokens, labels = self.sentences[idx]
        return {"text": tokens, "label": labels}


class IObTrainer(Trainer):

    def __init__(self,
                 **kwargs
                 ):
        super().__init__(task_type=TaskType.TOKEN, **kwargs)
        self.pad_label = "O"
        self.scheduler_name = kwargs.get("scheduler_name", "cosine")
        self.warmup_ratio = kwargs.get("warmup_ratio", 0.15)
        self.cache = []

    def _create_clf_params(self, **kwargs):
        return TokenClassificationParams(
            **self.params,
        )

    def _create_clf(self) -> torch.nn.Module:
        return TokenClassificationHead(
            hidden_size=self.embedding_dim,
            num_labels=self.num_labels,
            weights=self.weights if self.clf_params.use_class_weights else None,
            idx2label=self.idx2label,
            **self.clf_params.model_dump()
        )

    def prepare_data(self):
        if self.val_dataset is None:
            val_size = max(1, int(len(self.train_dataset) * 0.1))
            train_size = len(self.train_dataset) - val_size
            self.train_dataset, self.val_dataset = random_split(self.train_dataset,
                                                                [train_size, val_size],
                                                                generator=torch.Generator().manual_seed(42))
        self.train_dataloader = DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            collate_fn=token_classification_collate,
        )
        self.val_dataloader = DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            collate_fn=token_classification_collate,
        )

        labels = []
        for o in self.train_dataset:
            labels.append(o["label"])

        weights = []
        label_counts = Counter(label for sent in labels for label in sent)
        num_labels = len(label_counts)
        total = sum(label_counts.values())
        for idx in range(num_labels):
            lbl = self.idx2label[idx]
            freq = label_counts[lbl] / total
            w = 1.0 / (freq + 1e-8)
            weights.append(w)

        weights = torch.tensor(weights, device=self.device, dtype=torch.float32)
        self.weights = weights
        self.weights = weights / weights.mean()

    def _train_impl(self):
        if len(self.cache) == 0:
            logger.info("Caching training data...")
            for batch in self.train_dataloader:
                self.cache.append(self.prepare_batch(batch))
            logger.info("Completed")

        optimizer = torch.optim.AdamW(
            self.clf.parameters(),
            lr=self.lr,
            weight_decay=0.01
        )
        num_training_steps = len(self.train_dataloader) * self.num_epochs
        num_warmup_steps = int(num_training_steps * self.warmup_ratio)
        if self.scheduler_name == "linear":
            scheduler = get_linear_schedule_with_warmup(optimizer,
                                                        num_warmup_steps=num_warmup_steps,
                                                        num_training_steps=num_training_steps)
        else:
            scheduler = get_cosine_schedule_with_warmup(
                optimizer,
                num_warmup_steps=num_warmup_steps,
                num_training_steps=num_training_steps
            )

        best_span_f1 = float("-inf")
        best_token_f1 = float("-inf")
        best_score = float("-inf")
        patience_counter = 0
        self.best_model = None

        epoch = 0
        for epoch in tqdm(range(self.num_epochs), disable=not self.is_trial):
            self.train_one_epoch(
                optimizer=optimizer,
                scheduler=scheduler,
            )

            metrics = self.eval_one_epoch()
            span_f1 = metrics["span_f1"]
            token_f1 = metrics["token_f1"]

            # Early stopping on span-level F1
            score = 2 * span_f1 + token_f1
            # if span_f1 > best_span_f1 + 1e-4 or token_f1 > best_token_f1 + 1e-4:
            if score > best_score + 1e-4:
                logger.info(
                    f"\nSpan-F1 {best_span_f1:.4f} => {span_f1:.4f}\nToken-F1 {best_token_f1:.4f} => {token_f1:.4f}\nSaving model..."
                )
                best_span_f1 = max(best_span_f1, span_f1)
                best_token_f1 = max(best_token_f1, token_f1)
                best_score = max(best_score, 2 * best_span_f1 + best_token_f1)
                patience_counter = 0
                self.best_model = {k: v.detach().cpu().clone() for k, v in self.clf.state_dict().items()}
            else:
                patience_counter += 1
                logger.info(f"No improvement in span-F1. Patience {patience_counter}/{self.patience}")
                if patience_counter >= self.patience:
                    logger.info("Early stopping triggered on span-level F1.")
                    break

            if not self.is_trial:
                metrics["best_span_f1"] = best_span_f1
                metrics["best_token_f1"] = best_token_f1
                self.print_metrics(metrics, epoch)

        return epoch

    def eval_one_epoch(self) -> Dict[str, Any]:
        self.clf.eval()
        total_loss = 0.0
        all_gold: List[List[str]] = []
        all_pred: List[List[str]] = []
        all_text: List[List[str]] = []

        with torch.no_grad():
            batch: Dict[str, Any]
            for batch in tqdm(self.val_dataloader,
                              total=len(self.val_dataloader),
                              disable=self.is_trial,
                              desc="Evaluating"):
                batch_inputs = self.prepare_batch(batch)

                emb = batch_inputs["embeddings"]
                aligned_labels = batch_inputs["labels"]
                mask = batch_inputs["mask"]
                word_ids_batch = batch_inputs["word_ids"]

                # Forward pass — return_logits includes raw logits
                logits, loss = self.clf(
                    hidden=emb,
                    labels=aligned_labels,
                    mask=mask,
                    return_logits=True,
                )
                total_loss += loss.item()

                # Realign predictions + gold to word-level using embedder mapping
                sentences = batch["text"]
                gold_labels_batch = batch["label"]

                full_pred = logits.argmax(dim=-1).tolist()  # (B, T)

                for b, word_ids in enumerate(word_ids_batch):
                    full_pred_ids = full_pred[b]
                    restored_labels = []
                    prev_wid = None
                    for tid, wid in enumerate(word_ids):
                        if wid is None or wid == prev_wid:
                            continue
                        else:
                            restored_labels.append(self.idx2label[full_pred_ids[tid]])
                        prev_wid = wid

                    all_pred.append(repair_bio_seq(restored_labels))

                all_text.extend(sentences)
                all_gold.extend([repair_bio_seq(lbls) for lbls in gold_labels_batch])

        avg_loss = total_loss / max(1, len(self.val_dataloader))
        s_prec = seqeval.metrics.precision_score(all_gold, all_pred)
        s_rec = seqeval.metrics.recall_score(all_gold, all_pred)
        s_f1 = seqeval.metrics.f1_score(all_gold, all_pred)
        t_prec, t_rec, t_f1, _ = precision_recall_fscore_support(flatten(all_gold),
                                                                 flatten(all_pred),
                                                                 average='macro',
                                                                 zero_division=0)

        return {
            "loss": avg_loss,
            "span_precision": s_prec,
            "span_recall": s_rec,
            "span_f1": s_f1,
            "token_precision": t_prec,
            "token_recall": t_rec,
            "token_f1": t_f1,
            "sample_text": all_text[:5],
            "sample_gold": all_gold[:5],
            "sample_pred": all_pred[:5],
        }

    def print_metrics(self, metrics: Dict[str, Any], epoch=-1, file=sys.stdout):
        loss = metrics["loss"]
        best_span_f1 = metrics.get("best_span_f1", metrics["span_f1"])
        best_token_f1 = metrics.get("best_token_f1", metrics["token_f1"])
        span_precision = metrics["span_precision"]
        span_recall = metrics["span_recall"]
        span_f1 = metrics["span_f1"]
        token_precision = metrics["token_precision"]
        token_recall = metrics["token_recall"]
        token_f1 = metrics["token_f1"]
        sample_text = metrics["sample_text"]
        sample_gold = metrics["sample_gold"]
        sample_pred = metrics["sample_pred"]
        if epoch >= 0:
            print(f"\n===== EPOCH {epoch + 1} RESULTS =====", file=file)
        else:
            print("\n===== FINAL TEST RESULTS =====", file=file)
        print(f"     Loss: {loss:.4f}", file=file)
        print("-------------------------------", file=file)
        print(f" Token P: {token_precision:.4f}", file=file)
        print(f" Token R: {token_recall:.4f}", file=file)
        print(f"Token F1: {token_f1:.4f} (best: {best_token_f1:.4f})", file=file)
        print("-------------------------------", file=file)
        print(f" Span P: {span_precision:.4f}", file=file)
        print(f" Span R: {span_recall:.4f}", file=file)
        print(f"Span F1: {span_f1:.4f} (best: {best_span_f1:.4f})", file=file)
        print("\n--- SAMPLE PREDICTIONS ---", file=file)
        for tokens, gold_seq, pred_seq in zip(sample_text, sample_gold, sample_pred):
            longest_label = max(len(lbl) for lbl in itertools.chain(pred_seq, gold_seq))
            print("Tokens:     ", " ".join(tokens), file=file)
            print("Gold:       ", " ".join(f"{lbl:<{longest_label}}" for lbl in gold_seq), file=file)
            print("Predicted:  ", " ".join(f"{lbl:<{longest_label}}" for lbl in pred_seq), file=file)
            print("-" * 80, file=file)

    def train_one_epoch(self,
                        optimizer: torch.optim.Optimizer,
                        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None):
        self.clf.train()
        total_loss = 0.0

        # for batch in tqdm(self.train_dataloader, total=len(self.train_dataloader), desc="  Training"):
        for batch in tqdm(range(len(self.train_dataloader)),
                          disable=self.is_trial,
                          desc="  Training"):
            batch_inputs = self.cache[batch]
            # batch_inputs = self.prepare_batch(batch)

            emb = batch_inputs["embeddings"]
            labels = batch_inputs["labels"]
            mask = batch_inputs["mask"]

            _, loss = self.clf(
                hidden=emb,
                labels=labels,
                mask=mask,
            )

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.clf.parameters(), 5.0)
            optimizer.step()
            if scheduler is not None:
                scheduler.step()

            total_loss += loss.item()

        avg_loss = total_loss / max(1, len(self.train_dataloader))
        return avg_loss

    def prepare_batch(
        self,
        batch,
    ) -> Dict[str, Any]:
        sentences = batch["text"]
        gold_labels = batch["label"]
        emb_result = self.embedder(
            sentences,
            is_split_into_words=True,
        )
        padded_embeddings, padded_mask = emb_result.padded_token_embeddings_with_mask()

        embeddings = torch.from_numpy(padded_embeddings).type(torch.float32).to(self.device)
        mask = torch.from_numpy(padded_mask).type(torch.bool).to(self.device)

        B = len(sentences)
        max_T = padded_embeddings.shape[1]

        aligned_labels = torch.full(
            (B, max_T),
            fill_value=-100,
            dtype=torch.long,
            device=self.device,
        )

        word_ids_list = [m.word_ids for m in emb_result.mapping]
        for b, (word_ids, gold_seq) in enumerate(zip(word_ids_list, gold_labels)):
            prev_word = None
            for sub_idx, word_id in enumerate(word_ids):
                if word_id is None:
                    continue
                if word_id != prev_word:
                    aligned_labels[b, sub_idx] = self.label2idx[gold_seq[word_id]]

                prev_word = word_id

        return {
            "embeddings": embeddings,  # [B, T, H]
            "labels": aligned_labels,  # [B, T]
            "mask": mask,  # [B, T]
            "word_ids": word_ids_list,
        }
