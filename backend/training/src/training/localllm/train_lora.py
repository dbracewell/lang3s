# ruff: noqa: I001
import os
from unsloth import FastLanguageModel, get_chat_template
import torch
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForLanguageModeling
import argparse


def main():
    parser = argparse.ArgumentParser(description="Unsloth Fine-tuning for Qwen 2.5")
    parser.add_argument(
        "--json_path",
        type=str,
        required=True,
        help="Path to your ChatML JSON file",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",
        help="Base model",
    )
    parser.add_argument(
        "--output_dir", type=str, default="./outputs", help="Output directory"
    )
    parser.add_argument("--rank", type=int, default=64, help="LoRA Rank (r)")
    parser.add_argument("--alpha", type=int, default=128, help="LoRA Alpha")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning Rate")
    parser.add_argument(
        "--epochs", type=int, default=1, help="Number of training epochs"
    )
    args = parser.parse_args()

    # 1. Load Model and Tokenizer
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=16_000,
        load_in_4bit=True,
    )

    # 2. Add LoRA Adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.rank,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=args.alpha,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    tokenizer = get_chat_template(tokenizer, chat_template="chatml")

    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [
            tokenizer.apply_chat_template(
                convo, tokenize=False, add_generation_prompt=False
            )
            for convo in convos
        ]
        # Return pure text strings. We let SFTTrainer handle the tokenization.
        return {"text": texts}

    dataset = load_dataset("json", data_files=args.json_path, split="train")

    # Crucial: Drop the 'messages' column so PyTorch's collator never sees nested dicts
    dataset = dataset.map(  # type: ignore
        formatting_prompts_func,
        batched=True,
        remove_columns=dataset.column_names,
    )

    class CleanCollator(DataCollatorForLanguageModeling):
        def __call__(self, features, return_tensors=None):
            # Intercept the batch and delete the string columns that TRL refuses to drop
            for feature in features:
                feature.pop("text", None)
                feature.pop("messages", None)
            # Pass the cleaned integers to PyTorch for padding
            return super().__call__(features, return_tensors)

    data_collator = CleanCollator(tokenizer=tokenizer, mlm=False)

    # 4. Trainer Configuration
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,  # Replaces 'tokenizer = tokenizer'
        train_dataset=dataset,
        dataset_text_field="text",  # Restored to satisfy SFTTrainer initialization
        max_seq_length=16_000,
        data_collator=data_collator,
        args=TrainingArguments(
            per_device_train_batch_size=4,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=args.output_dir,
        ),
    )

    # 5. Train
    print("Starting training...")
    trainer.train()
    model.save_pretrained(os.path.join(args.output_dir, "lora_adapter"))


if __name__ == "__main__":
    main()
