import json
import os

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

# ==========================================
# 1. Configuration Setup
# ==========================================
input_data_file = "train.jsonl"  # Your original ChatML file
formatted_data_file = "train_formatted.jsonl"  # The new file this script will create
output_model_dir = "./smollm-135m-json-3090"
model_id = "HuggingFaceTB/SmolLM2-135M"


# ==========================================
# 2. Data Conversion Function
# ==========================================
def convert_chatml_to_prompt_completion(input_path, output_path):
    """
    Reads a ChatML structured JSONL file and flattens it into an explicit
    Prompt/Completion format tailored for Document-to-JSON extraction.
    """
    print(f"Converting {input_path} to structured Prompt-Completion format...")
    converted_data = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            data = json.loads(line)
            messages = data.get("messages", [])

            system_msg, user_msg, assistant_msg = "", "", ""

            # Extract content based on roles
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                elif msg["role"] == "user":
                    user_msg = msg["content"]
                elif msg["role"] == "assistant":
                    assistant_msg = msg["content"]

            # Construct the exact prompt layout
            # Notice the distinct structural boundaries we use instead of ChatML tags
            prompt = f"{system_msg}\n\n### Document:\n{user_msg}\n\n### JSON:\n"
            completion = assistant_msg

            converted_data.append({"prompt": prompt, "completion": completion})

    # Save the new format to disk
    with open(output_path, "w", encoding="utf-8") as f:
        for item in converted_data:
            f.write(json.dumps(item) + "\n")

    print(
        f"Successfully saved {len(converted_data)} formatted examples to {output_path}.\n"
    )


# Run the conversion
if not os.path.exists(input_data_file):
    raise FileNotFoundError(
        f"Could not find {input_data_file}. Please ensure your dataset is in the directory."
    )
convert_chatml_to_prompt_completion(input_data_file, formatted_data_file)

# ==========================================
# 3. Load Tokenizer & Model
# ==========================================
print(f"Loading tokenizer and model: {model_id}...")
tokenizer = AutoTokenizer.from_pretrained(model_id)

# Set the pad token (required for batching)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,  # RTX 3090 native optimization
    device_map="auto",
)

# ==========================================
# 4. Prepare Dataset & Collator
# ==========================================
dataset = load_dataset("json", data_files={"train": formatted_data_file})


def add_text_column(example):
    """
    Applies the formatting directly to the dataset before training begins.
    """
    return {"text": example["prompt"] + example["completion"] + tokenizer.eos_token}


print("Formatting dataset...")
dataset = dataset.map(add_text_column)


def format_instruction_func(example):
    """
    Stitches the prompt and completion strings together into a single sequence
    for the model, ending with the critical EOS token.
    """
    texts = []
    for prompt, completion in zip(example["prompt"], example["completion"]):
        texts.append(f"{prompt}{completion}{tokenizer.eos_token}")
    return texts


# CRITICAL FIX: The Data Collator
# This strictly enforces that the model is ONLY punished for mistakes it makes
# after "### JSON:\n". It completely ignores the document text when calculating loss.
response_template = "### JSON:\n"
collator = DataCollatorForCompletionOnlyLM(response_template, tokenizer=tokenizer)

# ==========================================
# 5. Training Arguments (RTX 3090 Optimized)
# ==========================================
training_args = SFTConfig(
    output_dir=output_model_dir,
    num_train_epochs=4,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=8,
    optim="adamw_torch",
    learning_rate=5e-5,
    max_length=2048,
    packing=False,
    bf16=True,
    fp16=False,
    gradient_checkpointing=True,
    logging_steps=10,
    save_strategy="epoch",
    report_to="none",
    # NEW: Tell the trainer exactly which column contains the formatted text
    dataset_text_field="text",
)

# ==========================================
# 6. Initialize Trainer & Execute
# ==========================================
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset["train"],
    data_collator=collator,  # Still using our completion mask!
    args=training_args,
    processing_class=tokenizer,
    # REMOVED: formatting_func is now gone to satisfy TRL's strict requirements
)
print("\nStarting full fine-tuning...")
trainer.train()

# ==========================================
# 7. Final Output
# ==========================================
trainer.save_model(output_model_dir)
tokenizer.save_pretrained(output_model_dir)
print(
    f"\nTraining complete! Your production-ready model is saved at: {output_model_dir}"
)
