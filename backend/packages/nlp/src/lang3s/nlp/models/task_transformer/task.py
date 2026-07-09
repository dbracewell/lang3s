from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

import torch
from pydantic import BaseModel, Field, model_validator
from pydantic.config import ConfigDict

from lang3s.core import config
from lang3s.nlp.components.embedder import EmbeddingResult

from .heads import SentenceClassificationHead, TokenClassificationHead
from .typedefs import TaskType, TransformerResult


class CommonParams(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
    )
    use_adapter: bool = Field(
        default=True,
        description="Whether to use DORA/LORA or not.",
    )
    dora_rank: int = Field(
        default=8,
        description="The rank of the DoRA layer",
    )
    lora_rank: int = Field(
        default=4,
        description="The rank of the LORA layer",
    )
    use_attention: bool = Field(
        default=True,
        description="Whether to use attention or not.",
    )
    num_attention_heads: int = Field(
        default=2,
        description="The number of attention heads",
    )
    dropout: float = Field(
        default=0.15,
        description="The dropout rate of the attention layer.",
    )

    @model_validator(mode="after")
    def fix_attention(self) -> CommonParams:
        if self.num_attention_heads == 0:
            self.use_attention = False
        elif not self.use_attention:
            self.num_attention_heads = 0
        return self


class SentenceClassificationParams(CommonParams):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
    )
    min_confidence: float = Field(
        default=0,
        description="The minimum confidence level for a classification.",
    )
    default_class: Optional[str] = Field(
        default=None,
        description="The default class.",
    )
    ignore_classes: List[str] = Field(
        default_factory=list,
        description="The list of classes to not create annotations from.",
    )
    use_mixup: bool = Field(
        default=False,
        description="Whether to use mixup data augmentation or not.",
    )
    mixup_alpha: float = Field(
        default=0.2,
        description="The alpha parameter of the mixup.",
    )
    use_focal_loss: bool = Field(
        default=False,
        description="Whether to use focal loss or not.",
    )
    warmup_ratio: float = Field(
        default=0.1,
        description="The ratio of warmup examples.",
    )
    learning_rate: float = Field(
        default=3e-4,
        description="The learning rate of the optimizer",
    )


class TokenClassificationParams(CommonParams):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="ignore",
    )
    scheduler_name: Literal["cosine"] | Literal["linear"] = Field(
        default="cosine",
        description="The scheduler name.",
    )
    warmup_ratio: float = Field(
        default=0.15,
        description="The ratio of warmup examples.",
    )
    learning_rate: float = Field(
        default=1.2e-4,
        description="The learning rate of the optimizer",
    )
    window_radius: int = Field(
        default=2,
        description="The window radius of the attention layer.",
    )
    use_class_weights: bool = Field(
        default=False,
        description="Whether to use class weights or not.",
    )


class Task(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    type: TaskType
    annotation_type: str
    label2id: Dict[str, int]
    language: Optional[str] = None
    input_type: Literal["sentence", "token"] = "sentence"
    params: Union[SentenceClassificationParams, TokenClassificationParams]
    head: Optional[torch.nn.Module] = Field(default=None, exclude=True)

    @property
    def id2label(self) -> Dict[int, str]:
        return {v: k for k, v in self.label2id.items()}

    @model_validator(mode="before")
    @classmethod
    def dispatch_params(cls, data: Any) -> Any:
        """
        Intercepts and mutates raw data before Pydantic's core validation runs.
        """
        # If data isn't a dict (e.g., already instantiated model),
        # let Pydantic handle it
        if not isinstance(data, dict):
            return data

        task_type = data.get("type")
        params_data = data.get("params")

        # If missing required fields, skip dispatch and
        # let Pydantic throw its standard errors
        if not task_type or not params_data:
            return data

        # If params_data is already an object, skip
        if not isinstance(params_data, dict):
            return data

        # Resolve the type enum/string
        tt = TaskType(task_type) if not isinstance(task_type, TaskType) else task_type

        # Dispatch
        if tt.is_sentence_level():
            data["params"] = SentenceClassificationParams.model_validate(params_data)
        elif tt.is_token():
            data["params"] = TokenClassificationParams.model_validate(params_data)
        else:
            raise ValueError(f"Task type {task_type} is not supported")

        return data

    def load_model_head(self, path: str):
        label_list = [""] * len(self.label2id)
        for idx, label in self.id2label.items():
            label_list[idx] = label

        hidden_size = config.TOKEN_EMBEDDING_DIMENSION
        if self.input_type == "sentence":
            hidden_size = config.SEMANTIC_EMBEDDING_DIMENSION

        if self.type == TaskType.TOKEN:
            token_params: TokenClassificationParams = cast(
                TokenClassificationParams, self.params
            )
            self.head = TokenClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                **token_params.model_dump(),
            )
        else:
            sentence_params: SentenceClassificationParams = cast(
                SentenceClassificationParams, self.params
            )
            self.head = SentenceClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                task_type=self.type,
                **sentence_params.model_dump(),
            )

        if path is not None:
            self.head.load_state_dict(torch.load(f"{path}/{self.name}_head.pt"))  # type: ignore
        self.head.eval()  # type: ignore
        return self.head

    def to_labels(
        self,
        head_output: torch.Tensor | List[List[int]],
        mask: torch.Tensor | None,
        embedding: EmbeddingResult,
    ) -> TransformerResult:

        if self.type.is_sentence_level():
            sentence_params = cast(SentenceClassificationParams, self.params)
            min_confidence = sentence_params.min_confidence
            ignore_classes = sentence_params.ignore_classes
            default_class = sentence_params.default_class

            if self.type == TaskType.SENTENCE_MULTILABEL:
                probs = torch.sigmoid(head_output)  # type: ignore
                predictions = (probs >= min_confidence).int().cpu().tolist()
                labels = []
                for prediction in predictions:
                    row_label = []
                    row_probs = []
                    for index, value in enumerate(prediction):
                        if value == 0:
                            continue
                        label_str = self.id2label[index]
                        if label_str not in ignore_classes:
                            row_label.append(label_str)
                            row_probs.append(probs[index].item())
                    labels.append((row_label, row_probs))
                return labels

            if self.type == TaskType.SENTENCE:
                probs = torch.softmax(head_output, dim=-1)  # type: ignore
                predictions = torch.argmax(probs, dim=-1).cpu().tolist()
                labels = []
                for i, label in enumerate(predictions):
                    if probs[i][label] >= min_confidence:
                        label_str = self.id2label[label]
                        if label_str not in ignore_classes:
                            labels.append((label_str, probs[i][label].item()))
                    else:
                        labels.append((default_class, 0))
                return labels

        return decode_token_labels(
            logits=head_output,  # type: ignore
            mask=mask,  # type: ignore
            idx2label=self.id2label,
            word_ids_list=[m.word_ids for m in embedding.mapping],
        )


def bio_to_spans(labels: List[str]) -> List[Tuple[str, int, int]]:
    """
    BIO → spans in [start, end) format.
    """
    spans = []
    start = None
    ent_type = None

    for i, tag in enumerate(labels):
        if tag == "O" or not tag:
            if ent_type is not None:
                spans.append((ent_type, start, i))  # i is end index
                ent_type = None
                start = None
            continue

        if "-" not in tag:
            if ent_type is not None:
                spans.append((ent_type, start, i))
                ent_type = None
                start = None
            continue

        prefix, typ = tag.split("-", 1)

        if prefix == "B":
            if ent_type is not None:
                spans.append((ent_type, start, i))
            ent_type = typ
            start = i

        elif prefix == "I":
            if ent_type != typ:
                if ent_type is not None:
                    spans.append((ent_type, start, i))
                ent_type = typ
                start = i

    if ent_type is not None:
        spans.append((ent_type, start, len(labels)))

    return spans


def repair_bio_seq(labels: list[str]) -> list[str]:
    fixed = []
    prev = "O"
    for tag in labels:
        if tag.startswith("I-"):
            t_type = tag[2:]
            if prev == "O" or (not prev.endswith(t_type)):
                tag = "B-" + t_type
        fixed.append(tag)
        prev = tag
    return fixed


def decode_token_labels(logits, mask, word_ids_list, idx2label):
    outputs = []
    mask = mask.bool()
    predictions = logits.argmax(dim=-1).tolist()
    for b, word_ids in enumerate(word_ids_list):
        pred = predictions[b]
        labels = []
        prev_wid = None
        for tid, wid in enumerate(word_ids):
            if not mask[b][tid]:
                continue

            if wid is None or wid == prev_wid:
                continue
            else:
                labels.append(idx2label[pred[tid]])
            prev_wid = wid

        outputs.append(bio_to_spans(repair_bio_seq(labels)))

    return outputs
