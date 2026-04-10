import os
import pickle
import random
import traceback
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset, Sampler, random_split
from tqdm import tqdm
from transformers import DataCollatorForSeq2Seq, get_cosine_schedule_with_warmup

from lang3s import config
from lang3s.models.text_generator import FineTunedLongT5


class LengthGroupedBatchSampler(Sampler):
    def __init__(self, dataset: list[dict], batch_size: int, drop_last: bool = False):
        super().__init__(dataset)
        self.batch_size = batch_size
        self.drop_last = drop_last
        self.lengths = [len(example["input_ids"]) for example in dataset]

    def __iter__(self):
        indices = list(range(len(self.lengths)))

        # 1. Add noise to lengths for epoch-to-epoch stochasticity
        # A variance of +/- 20 tokens ensures similar lengths are grouped,
        # but the exact boundaries shift every time __iter__ is called.
        indices.sort(key=lambda i: self.lengths[i] + random.uniform(-20, 20))

        # 2. Chunk the sorted indices into batches
        batches = [
            indices[i : i + self.batch_size]
            for i in range(0, len(indices), self.batch_size)
        ]

        # 3. Handle the final incomplete batch if requested
        if self.drop_last and len(batches[-1]) < self.batch_size:
            batches.pop()

        # 4. Shuffle the order of the batches so the model doesn't
        # always see short sequences first and long sequences last.
        random.shuffle(batches)

        # Yield the grouped batch indices
        for batch in batches:
            yield batch

    def __len__(self):
        if self.drop_last:
            return len(self.lengths) // self.batch_size
        else:
            return (len(self.lengths) + self.batch_size - 1) // self.batch_size


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
BATCH_SIZE = 32
ACCUMULATION_STEPS = 2
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
        model=model.model,
        label_pad_token_id=-100,
        padding=True,
    )

    train_dataset, val_dataset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),  # Ensures the same split every run
    )

    batch_sampler = LengthGroupedBatchSampler(
        dataset=train_dataset,  # type:ignore
        batch_size=BATCH_SIZE,
        drop_last=False,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_sampler=batch_sampler,
        collate_fn=collator,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        collate_fn=collator,
    )

    total_steps = len(train_loader) * TOTAL_EPOCHS
    warmup_steps = int(total_steps * WARMUP_FACTOR)

    model.model.config.use_cache = False
    model.model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )

    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)

    # Attach directly to the base input embeddings, bypassing any wrapper bugs
    if hasattr(model.model, "get_input_embeddings"):
        model.model.get_input_embeddings().register_forward_hook(
            make_inputs_require_grad
        )

    model.model.enable_input_require_grads()
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=LEARNING_RATE)

    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    global_step = 0
    for epoch in range(TOTAL_EPOCHS):
        loop = tqdm(train_loader, desc=f"Epoch {epoch}")
        total_loss = 0
        optimizer.zero_grad()

        for i, batch in enumerate(loop):
            model.train()
            input_ids = batch["input_ids"].to(DEVICE)
            attention_mask = batch["attention_mask"].to(DEVICE)
            labels = batch["labels"].to(DEVICE)

            outputs = model(
                input_ids=input_ids, attention_mask=attention_mask, labels=labels
            )
            loss = outputs.loss / ACCUMULATION_STEPS

            loss.backward()

            loss_val = loss.item() * ACCUMULATION_STEPS
            total_loss += loss_val

            del outputs
            del input_ids
            del attention_mask
            del labels
            del loss

            if (i + 1) % ACCUMULATION_STEPS == 0 or (i + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

                global_step += 1

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if torch.mps.is_available():
                    torch.mps.empty_cache()

                current_lr = scheduler.get_last_lr()[0]
                loop.set_postfix(loss=loss_val, lr=f"{current_lr:.6f}")

                if global_step % 5 == 0:
                    model.eval()
                    try:
                        # 4. INFERENCE MODE: Stricter memory constraints than no_grad()
                        with torch.inference_mode():
                            sample_input_ids = batch["input_ids"][0:1].to(DEVICE)
                            sample_attention_mask = batch["attention_mask"][0:1].to(
                                DEVICE
                            )

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
                                sample_labels, skip_special_tokens=True
                            )

                            print(f"\n[Step {global_step}]")
                            print(f"Actual: '{actual_target}'")
                            print(f"Debug Gen: '{output_text[0]}'")

                            del sample_input_ids
                            del sample_attention_mask
                            del output_text

                    except Exception as e:
                        print(f"Debug gen failed: {e}")
                        traceback.print_exc()

            del batch

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

                del outputs
                del input_ids
                del attention_mask
                del labels
                del batch

        avg_val_loss = val_loss / len(val_loader)
        print(
            f"\n*** Epoch {epoch} completed. Average Validation Loss: {avg_val_loss:.4f} ***\n"
        )

    model_file = os.path.join(config.MODELS_DIR, "long_t5")
    model.save_model(model_file)


if __name__ == "__main__":
    main()
