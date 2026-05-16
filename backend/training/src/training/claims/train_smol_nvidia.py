import os

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

# ==========================================
# 1. Configuration & Setup
# ==========================================
model_id = "HuggingFaceTB/SmolLM2-135M"
output_dir = "./smollm-135m-chatml-3090"

# ==========================================
# 2. Load Tokenizer & Add ChatML Tokens
# ==========================================
print(f"Loading tokenizer and model for {model_id}...")
tokenizer = AutoTokenizer.from_pretrained(model_id)

chatml_special_tokens = ["<|im_start|>", "<|im_end|>"]
tokenizer.add_special_tokens({"additional_special_tokens": chatml_special_tokens})

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

tokenizer.chat_template = (
    "{% for message in messages %}"
    "{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}"
    "{% endfor %}"
)

# ==========================================
# 3. Load Model (Optimized for 3090 Ampere)
# ==========================================
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,  # 3090 handles native BF16 flawlessly
    device_map="auto",  # Will target 'cuda:0' automatically
)
model.resize_token_embeddings(len(tokenizer))

# ==========================================
# 4. Load Dataset & Format Function
# ==========================================
dataset = load_dataset(
    "json",
    data_files={
        "train": os.path.expanduser("~/prj/data/claims/gpt-5.4-combined-claims.jsonl")
    },
)


def format_chatml_func(example):
    texts = []
    for messages in example["messages"]:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        texts.append(prompt)
    return texts


# ==========================================
# 5. Training Arguments (Nvidia Optimization)
# ==========================================
training_args = SFTConfig(
    output_dir=output_dir,
    num_train_epochs=3,
    per_device_train_batch_size=16,
    gradient_accumulation_steps=4,
    optim="adamw_torch",
    learning_rate=5e-5,
    max_length=4096,
    packing=False,
    bf16=True,
    fp16=False,
    gradient_checkpointing=False,
    logging_steps=10,
    report_to="none",
)

# ==========================================
# 6. Initialize Trainer & Train
# ==========================================
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset["train"],
    formatting_func=format_chatml_func,
    args=training_args,
    processing_class=tokenizer,
)

print("Starting lightning-fast training on RTX 3090...")
trainer.train()

# Save final outputs
trainer.save_model(output_dir)
tokenizer.save_pretrained(output_dir)
print(f"Training successfully finished. Saved to {output_dir}")
