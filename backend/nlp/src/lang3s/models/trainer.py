import json
import os
from typing import Optional

import torch
from torch.nn.utils.rnn import pad_sequence
from torch.optim.lr_scheduler import OneCycleLR
from torch.utils.data import DataLoader
from tqdm import tqdm

from lang3s import config
from lang3s.models.embedder import Embedder
from lang3s.models.transformer import MultiTaskTransformer
from .heads import TaskHead
from .helpers import align_labels
from .types import TaskType


def _train_one_epoch(
    dataloader: DataLoader,
    task_type: TaskType,
    device: str,
    head: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler.LRScheduler,
):
    embedder = Embedder()
    total_loss = 0
    for batch in tqdm(dataloader):
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


def train_task(
    task_name,
    annotation_type,
    dataset,
    label2id,
    task_type: TaskType,
    batch_size=8,
    num_epochs=3,
    lr=2e-4,
    language: Optional[str] = None,
):
    transformer = MultiTaskTransformer()
    embedder = Embedder()

    print(f"\n🚀 Training new task: {task_name} ({task_type})")

    # Create a save dir
    path = f"{config.ADAPTERS_DIR}/{task_name}"
    os.makedirs(path, exist_ok=True)

    num_labels = len(label2id)

    head = TaskHead(
        hidden_size=embedder.dimensions,
        num_labels=num_labels,
        task_type=task_type,
    ).to(transformer.device)

    optimizer = torch.optim.AdamW(list(head.parameters()), lr=lr)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    scheduler = OneCycleLR(
        optimizer,
        max_lr=lr,  # from LR Finder
        steps_per_epoch=len(dataloader),
        epochs=num_epochs
    )
    prev_loss = float("inf")
    head.train()
    for epoch in range(num_epochs):
        print(f"Epoch {epoch + 1}/{num_epochs}: lr={optimizer.param_groups[0]['lr']}")
        total_loss = _train_one_epoch(
            dataloader=dataloader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=transformer.device,
            head=head,
            task_type=task_type,
        )
        print(
            f"Epoch {epoch + 1} avg loss: {total_loss / len(dataloader):.4f}"
        )
        if prev_loss - total_loss < 0.001 * prev_loss:
            break
        else:
            prev_loss = total_loss

    # Save results
    print(f"💾 Saving adapter and head for task '{task_name}'")
    torch.save(head.state_dict(), f"{path}/{task_name}_head.pt")

    adapter = transformer.registry.register_task(
        task_name=task_name,
        task_type=task_type,
        label2id=label2id,
        annotation_type=annotation_type,
        language=language,
    )
    with open(f"{path}/{task_name}.config.json", "w") as fp:
        json.dump(adapter.to_json(), fp, indent=2)

    adapter.head = head
    print(f"✅ Task '{task_name}' trained and registered.")
