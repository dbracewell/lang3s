import enum
import json
import os
from typing import Dict, Optional

import torch
from pydantic import BaseModel, Field
from torch.utils.data.dataloader import DataLoader
from torch.utils.data.dataset import Dataset

from lang3s import config
from lang3s.models.embedder import Embedder
from lang3s.models.transformer.task import Task


class TrainerParams(BaseModel):
    name: str = Field(description="Name of the task, should be unique")
    data: str = Field(description="Path to the dataset")
    annotation_type: str = Field(description="The annotation type of the span created by this task")
    lang: Optional[str] = Field(default=None, description="The language supported by the classifier")
    num_epochs: int = Field(default=100, description="Number of epochs to train the model")
    learning_rate: float = Field(default=1e-4, description="The learning rate of the optimizer")
    patience: int = Field(default=5, description="The patience of the optimizer")
    batch_size: int = Field(default=32, description="The batch size of the optimizer")
    device: str = Field(default=config.TRAINING_DEVICE, description="The device of the model")
    label: str = Field(default="label", description="The label field in the dataset")
    text: str = Field(default="text", description="The text field in the dataset")
    validation_split: float = Field(default=0.1, description="The percentage of the dataset to use for validation")


class Lang3sDataset(Dataset):

    def __init__(self):
        self.label2idx: Dict[str, int] = {}
        self.idx2label: Dict[int, str] = {}

    def __len__(self):
        raise NotImplementedError()

    def __getitem__(self, idx: int):
        raise NotImplementedError()


class Trainer:

    def __init__(self,
                 name: str,
                 annotation_type: str,
                 dataset: Lang3sDataset,
                 lang: Optional[str] = None,
                 num_epochs: int = 20,
                 patience: int = 5,
                 batch_size: int = 32,
                 learning_rate: float = 1e-4,
                 device: str = config.TRAINING_DEVICE,
                 **kwargs):
        self.dataset = dataset
        self.embedder = Embedder()
        self.embedding_dim = self.embedder.dimensions
        self.num_epochs = num_epochs
        self.patience = patience
        self.patience_counter = 0
        self.name = name
        self.annotation_type = annotation_type
        self.lang = lang
        self.best_model = None
        self.lr = learning_rate
        self.batch_size = batch_size
        self.device = device
        self.params = {
            "name": self.name,
            "annotation_type": self.annotation_type,
            "lang": self.lang,
            "num_epochs": num_epochs,
            "patience": patience,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
        }
        for k, v in kwargs.items():
            if isinstance(v, str) or isinstance(v, int) or isinstance(v, float) or isinstance(v, bool) or isinstance(v,
                                                                                                                     enum.Enum):
                self.params[k] = v

    def _print_train_information(self, name: str, annotation_type: str):
        print(f"\n🚀 Training new task: {name} ({annotation_type})")
        print("\n" + "=" * 60)
        print("               TRAINING CONFIGURATION")
        print("=" * 60)

        # Pretty key-value alignment
        max_key_len = max(len(k) for k in self.params.keys())
        for key, value in self.params.items():
            print(f"{key:<{max_key_len}} : {value}")

        print("=" * 60 + "\n")

    def train(self):
        raise NotImplementedError()

    def eval_one_epoch(self,
                       dataloader: DataLoader,
                       epoch: int):
        raise NotImplementedError()

    def train_one_epoch(self,
                        dataloader: DataLoader,
                        epoch: int,
                        optimizer: torch.optim.Optimizer,
                        scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None):
        raise NotImplementedError()

    def save_model(self, task: Task):
        model_path = f"{config.ADAPTERS_DIR}/{self.name}"
        os.makedirs(model_path, exist_ok=True)
        print(f"💾 Saving adapter and head for task '{self.name}'.'")

        torch.save(self.best_model, f"{model_path}/{self.name}_head.pt")
        with open(f"{model_path}/{self.name}.config.json", "w") as fp:
            json.dump(task.to_json(), fp, indent=2)
