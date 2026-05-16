import json

from datasets import load_dataset
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainingArguments,
    Trainer,
)


def fine_tune_t5(
    jsonl_path,
    model_name="google/flan-t5-large",
    input_key="input",
    output_key="output",
    output_dir="./t5_finetuned_model",
):
    """
    Fine-tunes a T5 model on a JSONL dataset.

    Args:
        jsonl_path (str): Path to the .jsonl file.
        model_name (str): HuggingFace model ID (e.g., 'google/long-t5-tglobal-base').
        input_key (str): The key in JSONL containing the source text.
        output_key (str): The key in JSONL containing the target text.
        output_dir (str): Where to save the trained model.
    """

    # 1. Load the dataset
    print(f"Loading dataset from {jsonl_path}...")
    dataset = load_dataset("json", data_files=jsonl_path, split="train")

    # Split into train and validation (90/10)
    dataset = dataset.train_test_split(test_size=0.1)
    train_ds = dataset["train"]
    val_ds = dataset["test"]

    # 2. Load Tokenizer and Model
    print(f"Loading model: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

    def preprocess_function(examples):
        model_inputs = tokenizer(
            examples[input_key], max_length=2048, truncation=True, padding="max_length"
        )

        labels = tokenizer(
            text_target=examples[output_key],
            max_length=512,
            truncation=True,
            padding="max_length",
        )

        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    print("Tokenizing dataset...")
    tokenized_train = train_ds.map(
        preprocess_function, batched=True, remove_columns=train_ds.column_names
    )
    tokenized_val = val_ds.map(
        preprocess_function, batched=True, remove_columns=val_ds.column_names
    )

    # 4. Data Collator
    # This handles padding tokens in the labels by replacing them with -100
    # so the loss function ignores them during training.
    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)

    # 5. Training Arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        learning_rate=1e-5,
        per_device_train_batch_size=4,  # Adjust based on your GPU VRAM
        per_device_eval_batch_size=4,
        weight_decay=0.1,
        save_total_limit=2,
        num_train_epochs=3,
        predict_with_generate=True,
        max_grad_norm=1.0,
        logging_steps=10,
        push_to_hub=False,
        fp16=False,
        bf16=False,
    )

    # 6. Initialize Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_val,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    # 7. Train and Save
    print("Starting training...")
    trainer.train()

    print(f"Saving model to {output_dir}...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Done!")


# --- SCRIPT EXECUTION ---
if __name__ == "__main__":
    # CREATE A DUMMY DATASET FOR TESTING
    # In your real case, skip this part and point to your actual file.
    dummy_file = "data.jsonl"
    dummy_data = [
        {
            "input": "Translate to French: Hello, how are you?",
            "output": "Bonjour, comment allez-vous ?",
        },
        {
            "input": "Translate to French: The weather is nice.",
            "output": "Le temps est agréable.",
        },
        {"input": "Translate to French: I love coding.", "output": "J'aime coder."},
        {
            "input": "Translate to __target__: Good morning.",
            "output": "Bonjour.",
        },  # intentional error for testing
        {"input": "The capital of France is Paris.", "output": "Paris"},
        {"input": "The capital of Germany is Berlin.", "output": "Berlin"},
    ]
    # Note: I added a dummy line to show how it handles data.
    # Realistically, ensure your JSONL is clean.

    with open(dummy_file, "w", encoding="utf-8") as f:
        for entry in dummy_data:
            f.write(json.dumps(entry) + "\n")

    # Run the fine-tuning
    # Change 'input' and 'output' to match your JSONL keys
    fine_tune_t5(
        jsonl_path=dummy_file,
        model_name="google/flan-t5-small",  # Using small for quick testing
        input_key="input",
        output_key="output",
    )


def main():
    training_file = "/Users/ik/prj/data/claim_extraction_t5.jsonl"
    model_name = "google/long-t5-tglobal-base"
    fine_tune_t5(training_file, model_name, input_key="input", output_key="output")


if __name__ == "__main__":
    main()
