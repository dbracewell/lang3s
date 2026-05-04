import random
from typing import Any, Dict, List

import torch
import yaml
from datasets import load_dataset
from jsonlines import jsonlines
from pydantic import Field

from lang3s.app import Application
from lang3s.models.training.sentenceclf import SentenceClassifierTrainer
from lang3s.models.training.trainer import Lang3sDataset, TrainerParams
from lang3s.models.transformer.task import SentenceClassificationParams, TaskType


def read_text_file(path: str):
    sentences: List[str] = []
    labels: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "\t" not in line:
                continue
            index = line.rindex("\t")
            text = line[:index].strip()
            label = line[index + 1 :].strip()
            sentences.append(text)
            labels.append(label)
    return sentences, labels


def read_jsonl(path: str, text: str = "text", label: str = "label"):
    sentences: List[str] = []
    labels: List[str] = []
    with jsonlines.open(path, mode="r") as f:
        for doc in f:
            sentences.append(doc[text])
            labels.append(str(doc[label]))
    return sentences, labels


def run_trial(
    cfg, trial_id, parameters: Dict[str, Any], task_type, dataset, val_dataset
):
    params = SentenceClassificationParams(**parameters)
    params = params.model_dump()
    params["learning_rate"] = cfg["lr"]
    params["num_attention_heads"] = cfg["num_attention_heads"]
    params["dropout"] = cfg["dropout"]
    params["lora_rank"] = cfg["lora_rank"]
    params["dora_rank"] = cfg["dora_rank"]
    params["num_epochs"] = 5
    params["use_attention"] = cfg["use_attention"]
    params["use_adapter"] = True
    params["is_trial"] = True

    trainer = SentenceClassifierTrainer(
        name="test",
        annotation_type="test",
        task_type=task_type,
        **params,
        train_dataset=dataset,
        val_dataset=val_dataset,
    )
    trainer.train()
    result = trainer.eval_one_epoch()
    f1 = result["macro_f1"]
    print(f"[Trial {trial_id}] Macro F1={f1:.4f}  cfg={cfg}\n")
    return f1, params


def random_search(
    dataset: Lang3sDataset,
    val_dataset: Lang3sDataset | None,
    parameters: Dict[str, Any],
    task_type: TaskType,
    n_trials=5,
):
    search_space = {
        "lora_rank": [4, 6, 8, 10],
        "dora_rank": [8, 12, 16],
        "num_attention_heads": [2, 3, 4, 8],
        "use_attention": [True, False],
        "dropout": [0.05, 0.1, 0.15],
        "lr": [1e-4, 2e-4, 3e-4, 4e-4, 5e-4],
        "use_mixup": [True, False],
    }

    keys = list(search_space.keys())
    best = None
    seen = set()

    for t in range(1, n_trials + 1):
        while True:
            cfg = {k: random.choice(search_space[k]) for k in keys}
            if not cfg["use_attention"]:
                cfg["num_attention_heads"] = 0
            cfg_str = ", ".join(
                f"{k}={v}" for k, v in sorted(cfg.items(), key=lambda x: x[0])
            )
            if cfg_str not in seen:
                seen.add(cfg_str)
                break
        print(f"[Trial {t}] config={{{cfg_str}}}")
        result = run_trial(cfg, t, parameters, task_type, dataset, val_dataset)

        if best is None or result[0] > best[0]:
            best = result

    print("\nBEST CONFIG:", best)
    best_params = best[1]  # type: ignore
    best_params["is_trial"] = False
    return best_params


class SentenceClassificationDataset(Lang3sDataset):
    def __init__(
        self, path: str, task_type: TaskType, data_format: str, label: str, text: str
    ):
        super().__init__()
        if data_format == "text":
            sentences, labels = read_text_file(path)
        elif data_format == "json":
            sentences, labels = read_jsonl(path, text=text, label=label)
        else:
            raise ValueError(f"Format not supported: {data_format}")

        self.texts = sentences
        if task_type == TaskType.SENTENCE_MULTILABEL:
            self.multi_label = True
            if isinstance(labels[0], list):
                unique_labels = sorted(set(l for sublist in labels for l in sublist))
            else:
                unique_labels = sorted(set(labels))
                labels = [[label] for label in labels]
        else:
            self.multi_label = False
            unique_labels = sorted(set(labels))

        self.label2idx = {lbl: idx for idx, lbl in enumerate(unique_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

        if task_type == TaskType.SENTENCE_MULTILABEL:
            self.labels = []
            for lbl_list in labels:
                vec = torch.zeros(len(unique_labels), dtype=torch.float)
                for lbl in lbl_list:
                    if lbl in self.label2idx:
                        vec[self.label2idx[lbl]] = 1.0
                self.labels.append(vec)
        else:
            self.labels = [self.label2idx[lbl] for lbl in labels]  # type:ignore

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx: int):
        if isinstance(idx, list):
            return {
                "text": [self.texts[i] for i in idx],
                "label": torch.tensor(
                    [
                        self.labels[i]
                        if self.multi_label
                        else torch.tensor(self.labels[i], dtype=torch.long)
                        for i in idx
                    ],
                    dtype=torch.int64,
                ),
            }
        return {
            "text": self.texts[idx],
            "label": self.labels[idx]
            if self.multi_label
            else torch.tensor(self.labels[idx], dtype=torch.long),
        }


class HuggingFaceDataset(Lang3sDataset):
    def __init__(
        self, name: str, label: str = "label", text: str = "text", split: str = "train"
    ):
        super().__init__()
        self.dataset = load_dataset(name)[split]
        self.label = label
        self.text = text
        unique_labels = set(self.dataset[label])
        self.label2idx: Dict[str, int] = {l: i for i, l in enumerate(unique_labels)}
        self.idx2label = {v: k for k, v in self.label2idx.items()}

    def __len__(self):
        return len(self.dataset)  # type:ignore

    def __getitem__(self, idx: int):
        df = self.dataset[idx]  # type: ignore
        return {"text": df[self.text], "label": df[self.label]}


class ClfTrainer(Application, SentenceClassificationParams, TrainerParams):
    multilabel: bool = Field(default=False, description="Multilabel classification")
    format: str = Field(default="json", description="Format of the dataset")
    auto_config: bool = Field(
        default=False, description="Automatically determine hyperparameters."
    )
    auto_config_trials: int = Field(
        default=5,
        description="Number of trials to run when searching for hyperparameters.",
    )

    def run(self):
        parameters = dict(vars(self))
        parameters["task_type"] = (
            TaskType.SENTENCE_MULTILABEL if self.multilabel else TaskType.SENTENCE
        )
        if self.format == "hf":
            train_dataset = HuggingFaceDataset(
                name=self.train_data, label=self.label, text=self.text
            )
            val_dataset = HuggingFaceDataset(
                name=self.train_data, label=self.label, split="val"
            )
        else:
            train_dataset = SentenceClassificationDataset(
                task_type=parameters["task_type"],
                data_format=self.format,
                path=self.train_data,
                label=self.label,
                text=self.text,
            )
            if self.val_data is not None:
                val_dataset = SentenceClassificationDataset(
                    task_type=parameters["task_type"],
                    data_format=self.format,
                    path=self.val_data,
                    label=self.label,
                    text=self.text,
                )
            else:
                val_dataset = None

        if self.auto_config:
            best_parameters = random_search(
                train_dataset,
                val_dataset,
                parameters,
                parameters["task_type"],
                n_trials=self.auto_config_trials,
            )
            with open(f"{self.name}_best_parameters.yaml", "w") as f:
                yaml.dump(best_parameters, f, indent=2)
            parameters.update(best_parameters)

        trainer = SentenceClassifierTrainer(
            train_dataset=train_dataset,
            val_dataset=val_dataset,
            **parameters,
        )
        trainer.train()


if __name__ == "__main__":
    ClfTrainer.from_cli().run()
