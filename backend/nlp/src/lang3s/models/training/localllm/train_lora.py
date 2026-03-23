import argparse
import os

import torch
from datasets import load_dataset
from transformers import TrainingArguments
from trl import SFTTrainer
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template


def main():
    parser = argparse.ArgumentParser(description="Unsloth Fine-tuning for Qwen 2.5")
    parser.add_argument(
        "--json_path", type=str, required=True, help="Path to your ChatML JSON file"
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
    parser.add_argument(
        "--export_gguf", action="store_true", help="Export to GGUF at the end"
    )
    args = parser.parse_args()

    # 1. Load Model and Tokenizer
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model_name,
        max_seq_length=2048,
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

    # 3. Load and Format Dataset (ChatML)
    tokenizer = get_chat_template(tokenizer, chat_template="chatml")

    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [
            tokenizer.apply_chat_template(
                convo, tokenize=False, add_generation_prompt=False
            )
            for convo in convos
        ]
        return {"text": texts}

    dataset = load_dataset("json", data_files=args.json_path, split="train")
    dataset = dataset.map(formatting_prompts_func, batched=True)

    # 4. Trainer Configuration
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
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

    # 6. Save LoRA Adapter
    model.save_pretrained(os.path.join(args.output_dir, "lora_adapter"))

    # 7. Optional: Save to GGUF (Ready for llama-cpp-python)
    if args.export_gguf:
        print("Exporting to GGUF...")
        model.save_pretrained_gguf(
            os.path.join(args.output_dir, "gguf_model"),
            tokenizer,
            quantization_method="q4_k_m",
        )


if __name__ == "__main__":
    main()
