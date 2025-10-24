import json
import os.path
from collections import namedtuple
from typing import Dict, List, Set

import numpy as np
import torch
from adapters import AdapterFusionConfig, AutoAdapterModel
from transformers import (
    AutoConfig,  # pyright: ignore[reportPrivateImportUsage]
    AutoTokenizer,  # pyright: ignore[reportPrivateImportUsage]
)

from lang3s.config import (
    ADAPTER_CONFIG_FILE,
    ADAPTERS_DIR,
    BASE_ADAPTER_MODEL,
    DEVICE,
)

from .decoders import decode_labels

Adapter = namedtuple(
    "Adapter", ["name", "head", "dir", "type", "task", "language"]
)


def load_adapter_config() -> List[Adapter]:
    if os.path.exists(ADAPTER_CONFIG_FILE):
        adapters = []
        with open(ADAPTER_CONFIG_FILE) as f:
            adapter_config = json.load(f)
            for key, value in adapter_config.items():
                if not os.path.exists(
                    os.path.join(ADAPTERS_DIR, value.get("dir", key))
                ):
                    continue
                adapters.append(
                    Adapter(
                        name=key,
                        dir=value.get("dir", key),
                        head=value.get("head", key),
                        type=value["type"],
                        task=value["task"],
                        language=value["language"],
                    )
                )
        return adapters
    return []


AdapterOutput = namedtuple(
    "AdapterOutput",
    ["type", "task", "label"],
)


class AdapterModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            super().__init__()
            self.model_name = BASE_ADAPTER_MODEL
            self.config = AutoConfig.from_pretrained(BASE_ADAPTER_MODEL)
            self.model = AutoAdapterModel.from_pretrained(
                BASE_ADAPTER_MODEL, config=self.config
            )
            self.adapters = load_adapter_config()
            self.id2label: Dict[str, Dict[int, str]] = {}
            self.tokenizer = AutoTokenizer.from_pretrained(
                BASE_ADAPTER_MODEL,
                use_fast=True,
                add_prefix_space=True,
            )
            self.model.adapter_to("default", device=DEVICE)
            for adapter in self.adapters:
                self.model.load_adapter(
                    os.path.join(ADAPTERS_DIR, adapter.dir), with_head=True
                )
                head = self.model.heads[adapter.head]
                self.id2label[adapter.name] = {
                    v: k for k, v in head.config["label2id"].items()
                }
            fusion_config = AdapterFusionConfig(
                key=True,
                query=True,
                value=True,
                query_before_ln=True,
                regularization=True,
                residual_before=True,
                temperature=True,
                value_before_softmax=True,
                value_initialized="zeros",  # or "ones" or "uniform"
                dropout_prob=0.1,
            )
            self.model.add_adapter_fusion(
                adapter_names=[adapter.name for adapter in self.adapters],
                config=fusion_config,
                name="fusion_adapter",
                overwrite_ok=True,
                set_active=True,
            )
            self.model.to(DEVICE)
            self.initialized = True

    def tag(
        self,
        language: str,
        texts: List[str] | List[List[str]],
        annotation_types: Set[str] | None = None,
    ) -> List[AdapterOutput]:
        tok = self.tokenizer(
            texts,
            is_split_into_words=True,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        head_outputs: List[AdapterOutput] = []
        self.model.eval()
        with torch.no_grad():
            encoding = {k: v.to(DEVICE) for k, v in tok.items()}
            outputs = self.model(
                **encoding, output_hidden_states=True, device=DEVICE
            )
            hidden_states = outputs.hidden_states  # tuple of layer outputs
            last_hidden = hidden_states[-1]
            for adapter in self.adapters:
                if (
                    annotation_types is not None
                    and adapter.type not in annotation_types
                    and adapter.name not in annotation_types
                ):
                    continue
                if adapter.language != "" and adapter.language != language:
                    continue
                head = self.model.heads[adapter.head]
                logits = head((last_hidden,))[0].cpu().numpy()
                preds = np.argmax(logits, axis=-1)
                head_outputs.append(
                    AdapterOutput(
                        type=adapter.type,
                        task=adapter.task,
                        label=(
                            decode_labels(
                                preds, tok, self.id2label[adapter.name]
                            )
                            if adapter.task == "bio"
                            else [self.id2label[adapter.name][a] for a in preds]
                        ),
                    )
                )
        return head_outputs
