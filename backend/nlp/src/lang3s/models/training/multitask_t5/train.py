import os
import pickle
import textwrap
import traceback
from typing import Any

import jsonlines
import torch
from torch.utils.data import DataLoader, Dataset, random_split
from tqdm import tqdm
from transformers import DataCollatorForSeq2Seq, get_cosine_schedule_with_warmup

from lang3s import config
from lang3s.models.text_generator import FineTunedLongT5


class LongClaimDataset(Dataset):
    def __init__(
        self,
        path: str,
        tokenizer,
        max_source_length: int = 2048,
        max_target_length: int = 128,
    ) -> None:
        super().__init__()
        self.data = []
        self.tokenizer = tokenizer
        self.max_source_length = max_source_length
        self.max_target_length = max_target_length

        # Load data into memory
        with jsonlines.open(path) as reader:
            for obj in reader:
                prompt = textwrap.dedent(f"""Extract the claim from the TARGET given the TARGET and BEFORE and AFTER context:
                                             BEFORE: {obj["input"]["before_text"]}
                                             TARGET: {obj["input"]["target_text"]}
                                             AFTER: {obj["input"]["after_text"]}""")
                target = f"CLAIM:{obj['claim']}\tLABEL:{obj['label']}\tSOURCE:{obj['source']}"

                self.data.append(
                    {
                        "prompt": prompt,
                        "target": target,
                    }
                )

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        example = self.data[idx]

        # padding=False lets the DataCollator handle dynamic padding later
        model_inputs = self.tokenizer(
            example["prompt"],
            max_length=self.max_source_length,
            truncation=True,
            padding=False,
            return_tensors=None,  # Return lists instead of tensors for the collator
        )

        # Tokenize the target label
        labels = self.tokenizer(
            example["target"],
            max_length=self.max_target_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )

        model_inputs["labels"] = labels["input_ids"]
        return model_inputs


class T5Dataset(Dataset):
    def __init__(
        self,
        path: str,
    ) -> None:
        super().__init__()
        self.data = pickle.load(open(path, "rb"))

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        return self.data[idx]


LEARNING_RATE = 3e-4
TOTAL_EPOCHS = 5
WARMUP_FACTOR = 0.01
BATCH_SIZE = 8
DEVICE = config.TRAINING_DEVICE


def main():
    model = FineTunedLongT5().to(DEVICE)
    model.train()
    full_dataset = T5Dataset(
        path="/Users/ik/prj/data/t5_train",
    )

    total_size = len(full_dataset)
    train_size = int(0.9 * total_size)
    val_size = total_size - train_size

    collator = DataCollatorForSeq2Seq(
        tokenizer=model.tokenizer,
        model=model.model,  # Pass the underlying PEFT model
        label_pad_token_id=-100,  # Automatically ignores padding in loss
        padding="longest",
    )
    train_dataset, val_dataset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),  # Ensures the same split every run
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,  # Always shuffle training data
        collate_fn=collator,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,  # No need to shuffle validation data
        collate_fn=collator,
    )

    total_steps = len(train_loader) * TOTAL_EPOCHS
    warmup_steps = int(total_steps * WARMUP_FACTOR)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    global_step = 0
    for epoch in range(TOTAL_EPOCHS):
        loop = tqdm(train_loader, desc=f"Epoch {epoch}")
        total_loss = 0
        for batch in loop:
            model.train()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            optimizer.zero_grad()
            outputs = model(
                input_ids=input_ids, attention_mask=attention_mask, labels=labels
            )
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            current_lr = scheduler.get_last_lr()[0]

            loop.set_postfix(loss=loss.item(), lr=f"{current_lr:.6f}")

            global_step += BATCH_SIZE

            if global_step % (BATCH_SIZE * 5) == 0:
                model.eval()
                try:
                    with torch.no_grad():
                        sample_input_ids = batch["input_ids"][0:1].to(DEVICE)
                        sample_attention_mask = batch["attention_mask"][0:1].to(DEVICE)
                        output_text = model(
                            input_ids=sample_input_ids,
                            attention_mask=sample_attention_mask,
                            decode=True,
                            max_new_tokens=1024,
                        )
                        sample_labels = batch["labels"][0].clone()
                        sample_labels[sample_labels == -100] = (
                            model.tokenizer.pad_token_id
                        )
                        actual_target = model.tokenizer.decode(
                            sample_labels,
                            skip_special_tokens=True,
                        )

                        print(f"\n[Step {global_step}]")
                        print(f"Actual: '{actual_target}'")
                        print(f"Debug Gen: '{output_text[0]}'")
                except Exception as e:
                    print(f"Debug gen failed: {e}")
                    traceback.print_exc()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            val_loop = tqdm(val_loader, desc=f"Validation Epoch {epoch}")
            for val_batch in val_loop:
                input_ids = val_batch["input_ids"].to(DEVICE)
                attention_mask = val_batch["attention_mask"].to(DEVICE)
                labels = val_batch["labels"].to(DEVICE)

                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )

                val_loss += outputs.loss.item()
                val_loop.set_postfix(loss=outputs.loss.item())

        avg_val_loss = val_loss / len(val_loader)
        print(
            f"\n*** Epoch {epoch} completed. Average Validation Loss: {avg_val_loss:.4f} ***\n"
        )

    model_file = os.path.join(config.MODELS_DIR, "long_t5")
    model.save_model(model_file)


if __name__ == "__main__":
    main()
