from typing import Dict, List, Optional, Tuple

import torch
from torch.utils.data import random_split, DataLoader
from tqdm import tqdm

from lang3s.models.transformer.task import Task, TaskType, TokenClassificationParams, bio_to_spans
from .trainer import Lang3sDataset, Trainer


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
        super().__init__(**kwargs)
        self.pad_label = "O"
        self.best_span_f1 = 0.0
        self.best_model = None
        self.task = Task(
            name=self.name,
            annotation_type=self.annotation_type,
            type=TaskType.TOKEN,
            language=self.lang,
            label2id=self.dataset.label2idx,  # type: ignore
            params=TokenClassificationParams(lstm_hidden_dim=kwargs.get("lstm_hidden_dim", 256)),
        )
        self.clf = self.task.create_head(self.embedding_dim)
        self.clf.to(self.device)
        self.embedder.device = self.device
        self.weight_decay = kwargs.get("weight_decay", 0.1)
        self.params["weight_decay"] = kwargs.get("weight_decay", 0.1)

    def train(self):
        self._print_train_information(name=self.task.name, annotation_type=self.task.annotation_type)

        val_size = max(1, int(len(self.dataset) * 0.1))
        train_size = len(self.dataset) - val_size
        train_dataset, val_dataset = random_split(self.dataset, [train_size, val_size])
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

        optimizer = torch.optim.AdamW(
            self.clf.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )

        self.best_span_f1 = 0.0
        self.patience_counter = 0
        self.best_model = None

        for epoch in range(1, self.num_epochs + 1):
            self.train_one_epoch(
                epoch=epoch,
                dataloader=train_dataloader,
                optimizer=optimizer,
            )

            (
                val_loss,
                span_prec,
                span_rec,
                span_f1,
            ) = self.eval_one_epoch(
                epoch=epoch,
                dataloader=val_dataloader,
                print_samples=True,
            )

            # Early stopping on span-level F1
            if span_f1 > self.best_span_f1 + 1e-4:
                print(
                    f"Span-F1 improved from {self.best_span_f1:.4f} to {span_f1:.4f}. Saving model..."
                )
                self.best_span_f1 = span_f1
                self.patience_counter = 0
                self.best_model = self.clf.state_dict()
            else:
                self.patience_counter += 1
                print(f"No improvement in span-F1. Patience {self.patience_counter}/{self.patience}")
                if self.patience_counter >= self.patience:
                    print("Early stopping triggered on span-level F1.")
                    break
            print()

        self.save_model(self.task)

    def eval_one_epoch(self, dataloader: DataLoader, epoch: int, print_samples: bool = True):
        self.clf.eval()
        total_loss = 0.0
        all_gold: List[List[str]] = []
        all_pred: List[List[str]] = []
        all_text: List[List[str]] = []

        with torch.no_grad():
            for batch in tqdm(dataloader, total=len(dataloader), desc="Evaluating"):
                batch_inputs = self.prepare_batch(batch)

                emb = batch_inputs["embeddings"]
                labels = batch_inputs["labels"]
                mask = batch_inputs["mask"]

                loss = self.clf(
                    hidden=emb,
                    labels=labels,
                    mask=mask,
                )
                total_loss += loss.item()

                # CRF decoding
                pred_paths = self.clf(
                    hidden=emb,
                    mask=mask,
                    labels=None,
                )

                # Realign predictions + gold to word-level using embedder mapping
                sentences = batch["text"]
                gold_labels_batch = batch["label"]

                emb_eval = self.embedder(
                    sentences,
                    is_split_into_words=True,
                    agg="mean",
                )
                word_ids_batch = [m.word_ids for m in emb_eval.mapping]

                for b, (tokens, gold_seq, word_ids) in enumerate(
                    zip(sentences, gold_labels_batch, word_ids_batch)
                ):
                    # word-level gold is already correct
                    gold_seq_word = gold_seq

                    # predicted word-level labels: first subword for each token
                    pred_seq_word: List[str] = []
                    for word_idx in range(len(tokens)):
                        sub_positions = [i for i, w in enumerate(word_ids) if w == word_idx]
                        if not sub_positions:
                            pred_seq_word.append(self.pad_label)
                            continue
                        sub0 = sub_positions[0]
                        pred_label_id = pred_paths[b][sub0]
                        pred_seq_word.append(self.dataset.idx2label[pred_label_id])

                    all_text.append(tokens)
                    all_gold.append(gold_seq_word)
                    all_pred.append(pred_seq_word)

        avg_loss = total_loss / max(1, len(dataloader))
        print(f"Epoch {epoch} Val Loss: {avg_loss:.4f}")
        s_prec, s_rec, s_f1 = IObTrainer.compute_span_f1(all_gold, all_pred)
        print(f"Epoch {epoch} Span Precision:  {s_prec:.4f}")
        print(f"Epoch {epoch} Span Recall:     {s_rec:.4f}")
        print(f"Epoch {epoch} Span F1:         {s_f1:.4f}")

        if print_samples:
            print("\n--- SAMPLE PREDICTIONS ---")
            for i in range(min(3, len(all_text))):
                IObTrainer.print_predictions([all_text[i]], [all_gold[i]], [all_pred[i]])

        return avg_loss, s_prec, s_rec, s_f1

    @staticmethod
    def print_predictions(texts, gold, pred):
        for tokens, gold_seq, pred_seq in zip(texts, gold, pred):
            print("Tokens:     ", " ".join(tokens))
            print("Gold:       ", " ".join(gold_seq))
            print("Predicted:  ", " ".join(pred_seq))
            print("-" * 80)

    def train_one_epoch(self,
                        dataloader: DataLoader,
                        epoch: int,
                        optimizer: torch.optim.Optimizer,
                        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None):
        self.clf.train()
        total_loss = 0.0

        for batch in tqdm(dataloader, total=len(dataloader), desc="  Training"):
            batch_inputs = self.prepare_batch(batch)

            emb = batch_inputs["embeddings"]
            labels = batch_inputs["labels"]
            mask = batch_inputs["mask"]

            loss = self.clf(
                hidden=emb,
                labels=labels,
                mask=mask,
            )

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.clf.parameters(), 5.0)
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / max(1, len(dataloader))
        print(f"Epoch {epoch} Train Loss: {avg_loss:.4f}")
        return avg_loss

    @staticmethod
    def compute_span_f1(all_gold: List[List[str]], all_pred: List[List[str]]):
        """
        Compute span-level (chunk-level) precision, recall, F1
        over BIO segments.
        """
        gold_spans = []
        pred_spans = []

        for g_seq, p_seq in zip(all_gold, all_pred):
            gold_spans.extend(bio_to_spans(g_seq))
            pred_spans.extend(bio_to_spans(p_seq))

        gold_set = set(gold_spans)
        pred_set = set(pred_spans)

        tp = len(gold_set & pred_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)

        precision = tp / (tp + fp + 1e-9)
        recall = tp / (tp + fn + 1e-9)
        f1 = 2 * precision * recall / (precision + recall + 1e-9)

        return precision, recall, f1

    def prepare_batch(
        self,
        batch,
    ) -> Dict[str, torch.Tensor]:
        sentences = batch["text"]
        gold_labels = batch["label"]

        # 1) Run your long-sequence Embedder
        emb_result = self.embedder(
            sentences,
            is_split_into_words=True,
            agg="mean",
        )

        token_embeddings_list = emb_result.token_embeddings  # List[np.ndarray]
        word_ids_list = [m.word_ids for m in emb_result.mapping]

        B = len(sentences)
        max_T = max(arr.shape[0] for arr in token_embeddings_list)
        H = token_embeddings_list[0].shape[1]

        # 2) Pad embeddings + mask
        embeddings = torch.zeros((B, max_T, H), dtype=torch.float32, device=self.device)
        mask = torch.zeros((B, max_T), dtype=torch.bool, device=self.device)

        for b, arr in enumerate(token_embeddings_list):
            t = arr.shape[0]
            embeddings[b, :t] = torch.tensor(arr, dtype=torch.float32, device=self.device)
            mask[b, :t] = True

        # 3) Build subword-aligned label tensor
        aligned_labels = torch.full(
            (B, max_T),
            fill_value=self.dataset.label2idx[self.pad_label],
            dtype=torch.long,
            device=self.device,
        )

        for b, (word_ids, gold_seq) in enumerate(zip(word_ids_list, gold_labels)):
            for sub_idx, word_id in enumerate(word_ids):
                if word_id is None:
                    continue
                if word_id < len(gold_seq):
                    aligned_labels[b, sub_idx] = self.dataset.label2idx[gold_seq[word_id]]

        return {
            "embeddings": embeddings,  # [B, T, H]
            "labels": aligned_labels,  # [B, T]
            "mask": mask,  # [B, T]
        }
