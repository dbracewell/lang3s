import enum
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import torch
from pydantic import BaseModel, Field
from torch.utils.data.dataloader import DataLoader
from torch.utils.data.dataset import Dataset

from lang3s import config
from lang3s.models.embedder import Embedder
from lang3s.models.transformer.shared_types import TaskType
from lang3s.models.transformer.task import Task
from lang3s.utils.logger import get_logger


class TrainerParams(BaseModel):
    name: str = Field(description="Name of the task, should be unique")
    train_data: str = Field(description="Path to the training dataset")
    val_data: Optional[str] = Field(
        default=None, description="Path to the validation dataset"
    )
    annotation_type: str = Field(
        description="The annotation type of the span created by this task"
    )
    lang: Optional[str] = Field(
        default=None, description="The language supported by the classifier"
    )
    num_epochs: int = Field(
        default=40, description="Number of epochs to train the model"
    )
    patience: int = Field(default=5, description="The patience of the optimizer")
    batch_size: int = Field(default=16, description="The batch size of the optimizer")
    device: str = Field(
        default=config.TRAINING_DEVICE, description="The device of the model"
    )
    label: str = Field(default="label", description="The label field in the dataset")
    text: str = Field(default="text", description="The text field in the dataset")
    save_results: bool = Field(
        default=True,
        description="Whether to save the evaluation results of the training",
    )
    validation_split: float = Field(
        default=0.1,
        description="The percentage of the dataset to use for validation",
    )


class Lang3sDataset(Dataset):
    def __init__(self):
        self.label2idx: Dict[str, int] = {}
        self.idx2label: Dict[int, str] = {}

    def __len__(self):
        raise NotImplementedError()

    def __getitem__(self, idx: int):
        raise NotImplementedError()


logger = get_logger(__name__)


class Trainer:
    def __init__(
        self,
        name: str,
        annotation_type: str,
        train_dataset: Lang3sDataset,
        val_dataset: Lang3sDataset,
        task_type: TaskType,
        validation_split: float = 0.1,
        lang: Optional[str] = None,
        num_epochs: int = 20,
        patience: int = 5,
        batch_size: int = 32,
        learning_rate: float = 1e-4,
        save_results: bool = True,
        device: str = config.TRAINING_DEVICE,
        **kwargs,
    ):
        self.params = {
            "name": name,
            "annotation_type": annotation_type,
            "lang": lang,
            "num_epochs": num_epochs,
            "patience": patience,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
        }
        for k, v in kwargs.items():
            if (
                isinstance(v, str)
                or isinstance(v, int)
                or isinstance(v, float)
                or isinstance(v, bool)
                or isinstance(v, enum.Enum)
            ):
                self.params[k] = v

        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.val_dataloader: DataLoader = None  # type: ignore
        self.train_dataloader: DataLoader = None  # type:ignore

        self.idx2label = self.train_dataset.idx2label
        self.label2idx = self.train_dataset.label2idx
        self.num_labels = len(self.label2idx)

        self.validation_split = validation_split

        self.is_trial = kwargs.get("is_trial", False)
        if self.is_trial:
            logger.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.INFO)

        self.task_type = task_type
        self.embedder = Embedder()
        self.embedding_dim = config.TOKEN_EMBEDDING_DIMENSION
        self.num_epochs = num_epochs
        self.patience = patience
        self.name = name
        self.annotation_type = annotation_type
        self.lang = lang
        self.best_model = None
        self.lr = learning_rate
        self.batch_size = batch_size
        self.device = device
        self.save_results = save_results
        self.weights = None

        self.prepare_data()
        self.clf_params = self._create_clf_params(**kwargs)
        self.task = Task(
            name=self.name,
            annotation_type=self.annotation_type,
            type=self.task_type,
            language=self.lang,
            label2id=self.label2idx,
            params=self.clf_params,
        )
        self.clf: torch.nn.Module = self._create_clf()
        self.clf.to(self.device)
        self.embedder.device = self.device

    def _create_clf_params(self, **kwargs):
        raise NotImplementedError()

    def _create_clf(self) -> torch.nn.Module:
        raise NotImplementedError()

    def _print_train_information(
        self, name: str, annotation_type: str, file=sys.stdout
    ):
        print(f"\n🚀 Training new task: {name} ({annotation_type})", file=file)
        print("\n" + "=" * 60, file=file)
        print("               TRAINING CONFIGURATION", file=file)
        print("=" * 60, file=file)

        # Pretty key-value alignment
        max_key_len = max(len(k) for k in self.params.keys())
        for key, value in self.params.items():
            print(f"{key:<{max_key_len}} : {value}", file=file)

        print("=" * 60 + "\n", file=file)

    def prepare_data(self):
        raise NotImplementedError()

    def train(self):
        if not self.is_trial:
            self._print_train_information(
                name=self.name, annotation_type=self.annotation_type
            )

        last_epoch = self._train_impl()

        self.clf.load_state_dict(self.best_model)  # type: ignore
        self.clf.to(self.device)

        if not self.is_trial:
            metrics = self.eval_one_epoch()
            self.print_metrics(metrics)
            if self.save_results:
                with open(
                    f"{self.name}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    "w",
                ) as fp:
                    self._print_train_information(
                        name=self.name,
                        annotation_type=self.annotation_type,
                        file=fp,
                    )
                    print(f"Finished training in {last_epoch + 1} epochs", file=fp)
                    self.print_metrics(metrics, epoch=-1, file=fp)

        if not self.is_trial:
            self.save_model(self.task)

    def _train_impl(self) -> int:
        raise NotImplementedError()

    def print_metrics(self, metrics: Dict[str, Any], epoch=-1, file=sys.stdout):
        raise NotImplementedError()

    def eval_one_epoch(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def train_one_epoch(
        self,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    ):
        raise NotImplementedError()

    def save_model(self, task: Task):
        model_path = f"{config.ADAPTERS_DIR}/{self.name}"
        os.makedirs(model_path, exist_ok=True)
        print(f"💾 Saving adapter and head for task '{self.name}'.")

        torch.save(self.best_model, f"{model_path}/{self.name}_head.pt")
        with open(f"{model_path}/{self.name}.config.json", "w") as fp:
            json.dump(task.to_json(), fp, indent=2)
