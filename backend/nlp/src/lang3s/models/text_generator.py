import os

import numpy as np
import torch
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from torch import Tensor, nn
from transformers import (
    AutoTokenizer,
    LongT5ForConditionalGeneration,
    PreTrainedModel,
    PreTrainedTokenizer,
    T5ForConditionalGeneration,
    T5Tokenizer,
)

from lang3s.config import config

DEFAULT_T5_MODEL: str = "google/flan-t5-base"


class ProjectionLayer(nn.Module):
    def __init__(self, t5_dim=768, hidden_dim=1024):
        super().__init__()
        self.input_norm = nn.LayerNorm(3 * config.SEMANTIC_EMBEDDING_DIMENSION)
        self.proj = nn.Sequential(
            nn.Linear(3 * config.SEMANTIC_EMBEDDING_DIMENSION, hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, t5_dim),
            nn.LayerNorm(t5_dim),
        )

    def forward(self, tensor: Tensor) -> Tensor:
        return self.proj(self.input_norm(tensor))


DEFAULT_MODEL = "google/long-t5-tglobal-base"


class FineTunedLongT5(nn.Module):
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        lora_r: int = 32,
        lora_alpha: int = 64,
        lora_dropout: float = 0.05,
        adapter_path: str | None = None,
        use_gradient_checkpointing: bool = False,
    ):
        super().__init__()

        # LongT5 uses a specific tokenizer that handles its T-Global attention
        self.tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(model_name)
        self.base_model: PreTrainedModel = (
            LongT5ForConditionalGeneration.from_pretrained(model_name)
        )

        # Memory optimization for long sequences
        if use_gradient_checkpointing:
            self.base_model.gradient_checkpointing_enable()

        if adapter_path is not None:
            self.model = PeftModel.from_pretrained(self.base_model, adapter_path)
        else:
            # Standard LoRA targets for LongT5 attention blocks
            peft_config = LoraConfig(
                task_type=TaskType.SEQ_2_SEQ_LM,
                r=lora_r,
                lora_alpha=lora_alpha,
                lora_dropout=lora_dropout,
                use_dora=True,
                target_modules="all-linear",
            )
            self.model = get_peft_model(self.base_model, peft_config)

        if hasattr(self.model, "enable_input_require_grads"):
            self.model.enable_input_require_grads()
        else:

            def make_inputs_require_grad(module, input, output):
                output.requires_grad_(True)

            self.model.get_base_model().get_input_embeddings().register_forward_hook(
                make_inputs_require_grad
            )

    def save_model(self, path: str):
        os.makedirs(path, exist_ok=True)
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)

    @staticmethod
    def load_model(path: str, base_model_name: str = DEFAULT_MODEL):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Adapter path {path} not found.")
        return FineTunedLongT5(model_name=base_model_name, adapter_path=path)

    def generate(
        self,
        prompts: list[str],
        max_new_tokens: int = 128,
        num_beams: int = 4,
        repetition_penalty: float = 1.2,
    ) -> list[str]:
        model_inputs = self.tokenizer(
            prompts,
            truncation=True,
            padding=True,
            return_tensors="pt",
        ).to(next(self.model.parameters()).device)
        return self.forward(
            **model_inputs,
            decode=True,
            max_new_tokens=max_new_tokens,
            num_beams=num_beams,
            repetition_penalty=repetition_penalty,
        )

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor,
        labels: Tensor | None = None,
        decode: bool = False,
        max_new_tokens: int = 128,
        num_beams: int = 4,
        repetition_penalty: float = 1.2,
    ):
        if decode:
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                repetition_penalty=repetition_penalty,
                no_repeat_ngram_size=3,
                early_stopping=True,
            )
            return self.tokenizer.batch_decode(outputs, skip_special_tokens=True)

        # Training path: pass labels to calculate CrossEntropyLoss
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )
        return outputs


class TextGenerationModel(nn.Module):
    def __init__(
        self,
        t5_model: str = DEFAULT_T5_MODEL,
        lora_r=32,
        lora_alpha=128,
        lora_dropout=0.05,
        adapter_path: str | None = None,
    ):
        super().__init__()
        self.tokenizer = T5Tokenizer.from_pretrained(t5_model)
        self.base_model: PreTrainedModel = T5ForConditionalGeneration.from_pretrained(
            t5_model
        )

        if adapter_path is not None:
            self.t5 = PeftModel.from_pretrained(self.base_model, adapter_path)
        else:
            peft_config = LoraConfig(
                task_type=TaskType.SEQ_2_SEQ_LM,
                r=lora_r,
                lora_alpha=lora_alpha,
                lora_dropout=lora_dropout,
                target_modules=["q", "v", "k", "o"],
            )
            self.t5 = get_peft_model(self.base_model, peft_config)

        if hasattr(self.t5, "enable_input_require_grads"):
            self.t5.enable_input_require_grads()
        else:

            def make_inputs_require_grad(module, input, output):
                output.requires_grad_(True)

            self.t5.get_input_embeddings().register_forward_hook(
                make_inputs_require_grad
            )

        self.base_model.get_input_embeddings().requires_grad_(True)
        self.t5.enable_input_require_grads()
        self.base_model.shared.requires_grad_(False)

        self.projection = ProjectionLayer(t5_dim=self.t5.config.d_model)  # type:ignore

    def save_model(self, path: str):
        os.makedirs(path, exist_ok=True)
        torch.save(self.projection.state_dict(), os.path.join(path, "projection.pt"))
        self.t5.save_pretrained(os.path.join(path, "lora_adapters"))

    @staticmethod
    def load_model(path: str):
        if not os.path.exists(path):
            raise FileNotFoundError()
        model = TextGenerationModel(adapter_path=os.path.join(path, "lora_adapters"))
        model.projection.load_state_dict(
            torch.load(os.path.join(path, "projection.pt"))
        )
        return model

    def forward(
        self,
        tasks: str,
        embeddings: list[np.ndarray] | list[torch.Tensor],
        labels: Tensor | None = None,
        decode: bool = False,
        max_length: int = 512,
        min_length: int = 3,
        num_beans: int = 4,
        repetition_penalty: float = 1.2,
    ):
        device = next(self.projection.parameters()).device

        task_tokens = self.tokenizer(
            tasks,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        ).to(device)
        task_embeds = self.t5.get_input_embeddings()(task_tokens.input_ids)

        if isinstance(embeddings[0], np.ndarray):
            text_embeds = torch.stack([torch.as_tensor(e) for e in embeddings])
        else:
            text_embeds = embeddings

        text_embeds = text_embeds.to(device)
        projected_embeds = self.projection(text_embeds).unsqueeze(1).repeat(1, 128, 1)
        text_mask = torch.ones(
            (projected_embeds.size(0), 128),
            dtype=projected_embeds.dtype,
            device=device,
        )

        # combined_embeds = torch.cat([task_embeds, projected_embeds], dim=1)
        # combined_mask = torch.cat([task_tokens.attention_mask, text_mask], dim=1)
        combined_embeds = torch.cat([projected_embeds, task_embeds], dim=1)
        combined_mask = torch.cat([text_mask, task_tokens.attention_mask], dim=1).to(
            combined_embeds.dtype
        )

        if decode:
            encoder_outputs = self.t5.get_encoder()(
                inputs_embeds=combined_embeds,
                attention_mask=combined_mask,
            )
            outputs = self.t5.generate(
                encoder_outputs=encoder_outputs,
                attention_mask=combined_mask,
                decoder_start_token_id=self.t5.config.decoder_start_token_id,  # type:ignore
                max_length=max_length,
                min_length=min_length,
                num_beams=num_beans,
                no_repeat_ngram_size=3,
                repetition_penalty=repetition_penalty,
                early_stopping=True,
                return_dict_in_generate=True,
            )
            generated_ids = outputs.sequences
            return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)

        labels = labels.to(device)
        outputs = self.t5(
            inputs_embeds=combined_embeds,
            attention_mask=combined_mask,
            labels=labels,
        )
        return outputs
