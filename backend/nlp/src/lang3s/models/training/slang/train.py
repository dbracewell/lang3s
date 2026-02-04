import json

import evaluate
import numpy as np
import torch
from datasets import DatasetDict, load_dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from lang3s.data.filestore import FILE_STORE

# Configuration
DATA_FILE = str(FILE_STORE.get_file_path("slang_training_data.jsonl"))
MODEL_CHECKPOINT = "FacebookAI/xlm-roberta-base"
OUTPUT_DIR = FILE_STORE.get_file_path("slang-detector-model")
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
NUM_EPOCHS = 10
MAX_LENGTH = 256

# Set Device (MPS for Mac, CUDA for Nvidia, CPU fallback)
device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)
print(f"Using device: {device}")

# Label Definitions
# We map 0 -> "O" (Outside) and 1 -> "SLANG"
id2label = {0: "O", 1: "B-SLANG", 2: "I-SLANG"}
label2id = {"O": 0, "B-SLANG": 1, "I-SLANG": 2}
label_list = ["O", "B-SLANG", "I-SLANG"]


def tokenize_and_align_labels(examples):
    """
    The dataset contains word-level tokens (['The', 'fit', 'is', 'mid']).
    The tokenizer will split these into sub-words (['The', 'fit', 'is', 'mi', '##d']).
    We must realign the labels (0, 0, 0, 1) to match the sub-words.
    """
    tokenized_inputs = tokenizer(
        examples["tokens"],
        truncation=True,
        is_split_into_words=True,
        max_length=MAX_LENGTH,
    )

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            # Special tokens (CLS, SEP, PAD) map to None. We set label to -100 to ignore in loss.
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                # First sub-token of a word takes the real label
                label_ids.append(label[word_idx])
            else:
                # Subsequent sub-tokens of the same word also take the label
                # (We could set this to -100 to only train on the first sub-token,
                # but training on all is often better for dense supervision)
                label_ids.append(label[word_idx])
            previous_word_idx = word_idx
        labels.append(label_ids)

    tokenized_inputs["labels"] = labels
    return tokenized_inputs


def compute_metrics(p):
    """
    Calculates Span F1, Precision, and Recall using seqeval.
    """
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    # Remove ignored index (special tokens)
    true_predictions = [
        [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]

    results = metric.compute(predictions=true_predictions, references=true_labels)

    # Seqeval returns nested dicts if there are multiple types,
    # but here we just check overall or specific "SLANG" tag stats.
    return {
        "precision": results["overall_precision"],
        "recall": results["overall_recall"],
        "f1": results["overall_f1"],
        "accuracy": results["overall_accuracy"],
    }


def main():
    global tokenizer, metric

    # 1. Load Dataset
    print(f"Loading dataset from {DATA_FILE}...")
    try:
        raw_dataset = load_dataset("json", data_files=[DATA_FILE])
    except FileNotFoundError:
        print(f"Error: Could not find {DATA_FILE}. Did you run build_dataset.py?")
        return

    # 2. Split Dataset (Train: 80%, Validation: 10%, Test: 10%)
    # First split Train (80%) and Temp (20%)
    train_testvalid = raw_dataset["train"].train_test_split(test_size=0.2, seed=42)
    # Split Temp (20%) into Valid (10%) and Test (10%)
    test_valid = train_testvalid["test"].train_test_split(test_size=0.5, seed=42)

    datasets = DatasetDict(
        {
            "train": train_testvalid["train"],
            "validation": test_valid["train"],
            "test": test_valid["test"],
        }
    )
    print(
        f"Data splits: Train={len(datasets['train'])}, Val={len(datasets['validation'])}, Test={len(datasets['test'])}"
    )

    # 3. Tokenization & Alignment
    print("Initializing Tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_CHECKPOINT)

    print("Tokenizing and aligning labels...")
    tokenized_datasets = datasets.map(tokenize_and_align_labels, batched=True)

    # 4. Initialize Model
    print("Initializing Model...")
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_CHECKPOINT,
        num_labels=len(label_list),
        id2label=id2label,
        label2id=label2id,
    )
    model.to(device)

    # 5. Metrics
    metric = evaluate.load("seqeval")
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

    # 6. Training Arguments
    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",  # Evaluate every epoch
        save_strategy="epoch",
        learning_rate=LEARNING_RATE,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        num_train_epochs=NUM_EPOCHS,
        weight_decay=0.01,
        load_best_model_at_end=True,  # Load best model when finished
        metric_for_best_model="f1",  # Use F1 to determine "best"
        save_total_limit=2,  # Keep only last 2 checkpoints
        logging_steps=50,
        push_to_hub=False,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(early_stopping_patience=3)
        ],  # Stop if val_f1 doesn't improve for 3 epochs
    )

    # 7. Train
    print("Starting Training...")
    trainer.train()

    # 8. Evaluation on Test Set
    print("\n--- Final Evaluation on Test Set ---")
    test_results = trainer.evaluate(tokenized_datasets["test"])
    print(json.dumps(test_results, indent=2))

    # 9. Save Final Model
    print(f"Saving final model to {OUTPUT_DIR}/final...")
    trainer.save_model(f"{OUTPUT_DIR}/final")
    tokenizer.save_pretrained(f"{OUTPUT_DIR}/final")

    # 10. Quick Inference Check
    print("\n--- Manual Inference Check ---")
    inputs = tokenizer("The new update is absolutely goated.", return_tensors="pt").to(
        device
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    predictions = torch.argmax(logits, dim=2)[0].tolist()
    tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])

    print(f"Input: The new update is absolutely goated.")
    for token, pred in zip(tokens, predictions):
        if token not in tokenizer.all_special_tokens:
            label = label_list[pred]
            print(f"{token:<12} : {label}")


if __name__ == "__main__":
    main()
