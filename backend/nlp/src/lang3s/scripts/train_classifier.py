import argparse
import os
from typing import Dict, List

import numpy as np
from adapters import AdapterConfig, AdapterTrainer, AutoAdapterModel
from datasets import Dataset, DatasetDict
from transformers import (
    AutoConfig,
    AutoTokenizer,
    DataCollatorWithPadding,
    PreTrainedTokenizerFast,
    TrainingArguments,
)

from lang3s.config import (
    ADAPTERS_DIR,
    BASE_ADAPTER_MODEL,
    BIO_TRAIN_BATCH_SIZE,
    BIO_TRAIN_LR,
    BIO_TRAIN_NUM_EPOCHS,
    DEVICE,
)

from .common import update_adapter_config


def build_label_maps(dataset_dict: DatasetDict, labels_name: str = "labels"):
    labels = set()
    for split_name, split in dataset_dict.items():
        for example_labels in split[labels_name]:
            labels.update(example_labels)
    label_list = sorted(labels)
    id2label = {i: lab for i, lab in enumerate(label_list)}
    label2id = {lab: i for i, lab in id2label.items()}
    return label_list, label2id, id2label


def read_text_file(path: str):
    sentences = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "\t" not in line:
                continue
            index = line.rindex("\t")
            text = line[:index].strip()
            label = line[index + 1 :].strip()
            sentences.append({"text": text, "labels": label})
    return sentences


def load_text_dataset(task_files: dict, splits: List[str] | None = None):
    if splits is None:
        splits = ["train", "dev", "test"]
    dataset_splits = {}
    for split_name in splits:
        if split_name in task_files and task_files[split_name] is not None:
            dataset_splits[split_name] = Dataset.from_list(
                read_text_file(task_files[split_name])
            )
    return DatasetDict(dataset_splits)


def tokenize_examples(
    texts: List[str],
    labels: List[str],
    tokenizer: PreTrainedTokenizerFast,
    label2id: Dict[str, int],
):
    output = tokenizer(
        texts,
        truncation=True,
        max_length=512,
        padding=True,
        return_tensors="pt",
    )
    output["labels"] = [label2id[label] for label in labels]
    return output


def add_new_task_adapter(task_name: str, task_files: Dict[str, str]):
    print(f"\nAdding new adapter for task: {task_name}")

    tokenizer = AutoTokenizer.from_pretrained(
        BASE_ADAPTER_MODEL, use_fast=True, add_prefix_space=True
    )
    config = AutoConfig.from_pretrained(BASE_ADAPTER_MODEL)
    model = AutoAdapterModel.from_pretrained(BASE_ADAPTER_MODEL, config=config)
    model.to(DEVICE)
    raw_datasets = load_text_dataset(task_files)
    label_list, label2id, id2label = build_label_maps(raw_datasets)
    num_labels = len(label_list)
    print(f"Labels for {task_name}: {label_list}")
    tokenized_datasets = raw_datasets.map(
        lambda examples: tokenize_examples(
            examples["text"], examples["labels"], tokenizer, label2id
        ),
        batched=True,
        remove_columns=["text"],
    )

    train_dataset = tokenized_datasets.get("train", None)
    eval_dataset = tokenized_datasets.get("validation", None)

    adapter_config = AdapterConfig.load(
        "pfeiffer",
        reduction_factor=16,
        label2id=label2id,
        num_labels=num_labels,
        adapter_residual_before_ln=False,
        cross_adapter=False,
        inv_adapter=None,
        inv_adapter_reduction_factor=None,
        leave_out=[],
        ln_after=False,
        ln_before=False,
        mh_adapter=False,
        non_linearity="relu",
        original_ln_after=True,
        original_ln_before=True,
        output_adapter=True,
        residual_before_ln=True,
    )

    # Add adapter + head
    model.add_adapter(task_name, config=adapter_config)
    print(num_labels, id2label)
    model.add_classification_head(
        task_name, num_labels=num_labels, id2label=id2label
    )

    # Freeze everything except new adapter
    model.train_adapter(task_name)
    model.set_active_adapters(task_name)

    data_collator = DataCollatorWithPadding(tokenizer)
    label_list_by_id = [id2label[i] for i in range(num_labels)]

    def compute_metrics(p):
        predictions, labels = p
        preds = np.argmax(predictions, axis=2)
        true_predictions, true_labels = [], []
        for pred, lab in zip(preds, labels):
            cur_preds, cur_labels = [], []
            for p_i, l_i in zip(pred, lab):
                if l_i == -100:
                    continue
                cur_preds.append(label_list_by_id[p_i])
                cur_labels.append(label_list_by_id[l_i])
            true_predictions.append(cur_preds)
            true_labels.append(cur_labels)
        return {"true": true_predictions}

    training_args = TrainingArguments(
        learning_rate=BIO_TRAIN_LR,
        per_device_train_batch_size=BIO_TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=BIO_TRAIN_BATCH_SIZE,
        num_train_epochs=BIO_TRAIN_NUM_EPOCHS,
        weight_decay=0.01,
        save_total_limit=2,
        use_mps_device=True,
    )

    trainer = AdapterTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    if train_dataset is not None:
        print(f"Training adapter for task: {task_name}")
        trainer.train()

    model.save_adapter(os.path.join(ADAPTERS_DIR, task_name), task_name)
    model.save_head(os.path.join(ADAPTERS_DIR, task_name), task_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_name", help="Task name", required=True)
    parser.add_argument("--data", help="Data directory", required=True)
    parser.add_argument("--lang", help="Language", required=True)
    parser.add_argument("--type", help="Annotation type", required=True)
    args = parser.parse_args()
    add_new_task_adapter(
        args.task_name,
        {
            "train": os.path.join(args.data, "train.txt"),
            "validation": os.path.join(args.data, "dev.txt"),
        },
    )
    update_adapter_config(
        name=args.task_name,
        task="clf",
        language=args.lang,
        annotation_type=args.type,
    )
