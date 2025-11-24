import json
from typing import Any, Dict, Optional, List, Tuple, cast

import torch
import torch.nn as nn
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from pydantic.fields import computed_field

from lang3s.models.embedder import EmbeddingResult
from .heads import SentenceClassificationHead, TokenClassificationHead
from .shared_types import TaskType, TransformerResult


class SentenceClassificationParams(BaseModel):
    num_attention_heads: int = 0
    rank: int = 8
    alpha: int = 8
    min_confidence: float = 0
    default_class: Optional[str] = None
    ignore_classes: List[str] = Field(default_factory=list)
    use_dora: bool = True


class TokenClassificationParams(BaseModel):
    lstm_hidden_dim: int = Field(default=256)


class Task(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    name: str
    type: TaskType
    annotation_type: str
    label2id: Dict[str, int]
    language: Optional[str] = None
    params: SentenceClassificationParams | TokenClassificationParams
    head: Optional[torch.nn.Module] = None

    @classmethod
    def from_dict(cls, json_dict):
        return cls.model_validate(json_dict)

    @computed_field
    @property
    def id2label(self) -> Dict[int, str]:
        return {v: k for k, v in self.label2id.items()}

    def to_json(self):
        return self.model_dump(exclude={"head", "id2label"}, exclude_defaults=False)

    @classmethod
    def _dispatch_params(cls, data):
        """Normalize data → dict, determine correct Params subclass,
        and safely merge params back into the input."""

        # 1. Ensure data is a pure dict (handles ValidationData, ModelMapping, BaseModel, etc.)
        if not isinstance(data, dict):
            data = dict(data)

        task_type = data.get("type")
        if task_type is None:
            # cannot dispatch without type
            return data

        params_data = data.get("params")

        # 2. If params is already a Params instance → KEEP IT
        if isinstance(params_data, SentenceClassificationParams) or isinstance(params_data, TokenClassificationParams):
            return data

        # 3. Determine params subclass
        if TaskType(task_type).is_sentence_level():
            params_cls = SentenceClassificationParams
        elif TaskType(task_type).is_token():
            params_cls = TokenClassificationParams
        else:
            raise NotImplementedError(f"Task type {task_type} is not supported")

        # 4. Safely validate dictionary params
        parsed_params = params_cls.model_validate(params_data or {})

        # 5. Merge into a brand-new dict (NEVER use {**data})
        new_data = dict(data)
        new_data["params"] = parsed_params
        return new_data

    @classmethod
    def model_validate(cls, data, *,
                       strict: bool | None = None,
                       from_attributes: bool | None = None,
                       context: Any | None = None,
                       by_alias: bool | None = None,
                       by_name: bool | None = None):
        data = cls._dispatch_params(data)
        return super().model_validate(data,
                                      strict=strict,
                                      from_attributes=from_attributes,
                                      context=context,
                                      by_alias=by_alias, by_name=by_name)

    @classmethod
    def model_validate_json(cls, json_data: str, *,
                            strict: bool | None = None,
                            from_attributes: bool | None = None,
                            context: Any | None = None,
                            by_alias: bool | None = None,
                            by_name: bool | None = None):
        raw = json.loads(json_data)
        raw = cls._dispatch_params(raw)
        return super().model_validate(raw,
                                      strict=strict,
                                      from_attributes=from_attributes,
                                      context=context,
                                      by_alias=by_alias, by_name=by_name)

    def create_head(self,
                    hidden_size: int,
                    path: Optional[str] = None):

        label_list = [""] * len(self.label2id)
        for idx, label in self.id2label.items():
            label_list[idx] = label

        if self.type == TaskType.TOKEN:
            token_params: TokenClassificationParams = cast(TokenClassificationParams, self.params)
            self.head = TokenClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                lstm_hidden=token_params.lstm_hidden_dim,
                label2id=self.label2id,
            )
        else:
            sentence_params: SentenceClassificationParams = cast(SentenceClassificationParams, self.params)
            dummy_layer = nn.Linear(hidden_size, hidden_size)
            self.head = SentenceClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                task_type=self.type,
                original_layer=dummy_layer,
                rank=sentence_params.rank,
                alpha=sentence_params.alpha,
                num_attention_heads=sentence_params.num_attention_heads,
                use_dora=sentence_params.use_dora,
            )

        if path is not None:
            self.head.load_state_dict(
                torch.load(f"{path}/{self.name}_head.pt")
            )
        self.head.eval()
        return self.head

    def to_labels(self,
                  head_output: torch.Tensor | List[List[int]],
                  embedding: EmbeddingResult) -> TransformerResult:
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
            pred_paths=head_output,
            idx2label=self.id2label,
            pad_label='O',
            word_ids_list=[m.word_ids for m in embedding.mapping]
        )


class TaskOld(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    annotation_type: str
    name: str
    type: TaskType
    label2id: Dict[str, int]
    num_attention_heads: int = 0
    rank: int = 8
    alpha: int = 8
    language: Optional[str] = None
    min_confidence: float = 0
    default_class: Optional[str] = None
    ignore_classes: List[str] = Field(default_factory=list)
    lstm_hidden: Optional[int] = Field(default=256)
    head: Optional[torch.nn.Module] = None
    use_dora: bool = True

    @computed_field
    @property
    def id2label(self) -> Dict[int, str]:
        return {v: k for k, v in self.label2id.items()}

    def to_json(self):
        return self.model_dump(exclude={"head", "id2label"})

    @classmethod
    def from_dict(cls, json_dict):
        return cls.model_validate(json_dict)

    def create_head(self,
                    hidden_size: int,
                    device: torch.device | str = "cpu",
                    path: Optional[str] = None):

        label_list = [""] * len(self.label2id)
        for idx, label in self.id2label.items():
            label_list[idx] = label

        if self.type == TaskType.TOKEN:
            self.head = TokenClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                lstm_hidden=self.lstm_hidden or 256,
                label2id=self.label2id,
            )
        else:
            dummy_layer = nn.Linear(hidden_size, hidden_size)
            self.head = SentenceClassificationHead(
                hidden_size=hidden_size,
                num_labels=len(self.label2id),
                task_type=self.type,
                original_layer=dummy_layer,
                rank=self.rank,
                alpha=self.alpha,
                num_attention_heads=self.num_attention_heads,
                use_dora=self.use_dora,
            )

        if path is not None:
            self.head.load_state_dict(
                torch.load(f"{path}/{self.name}_head.pt", map_location=device)
            )
        self.head.to(device)
        self.head.eval()
        return self.head

    def to_labels(self,
                  head_output: torch.Tensor | List[List[int]],
                  embedding: EmbeddingResult) -> TransformerResult:

        if self.type == TaskType.SENTENCE_MULTILABEL:
            probs = torch.sigmoid(head_output)  # type: ignore
            predictions = (probs >= self.min_confidence).int().cpu().tolist()
            labels = []
            for prediction in predictions:
                row_label = []
                row_probs = []
                for index, value in enumerate(prediction):
                    if value == 0:
                        continue
                    label_str = self.id2label[index]
                    if label_str not in self.ignore_classes:
                        row_label.append(label_str)
                        row_probs.append(probs[index].item())
                labels.append((row_label, row_probs))
            return labels

        if self.type == TaskType.SENTENCE:
            probs = torch.softmax(head_output, dim=-1)  # type: ignore
            predictions = torch.argmax(probs, dim=-1).cpu().tolist()
            labels = []
            for i, label in enumerate(predictions):
                if probs[i][label] >= self.min_confidence:
                    label_str = self.id2label[label]
                    if label_str not in self.ignore_classes:
                        labels.append((label_str, probs[i][label].item()))
                else:
                    labels.append((self.default_class, 0))
            return labels

        return decode_token_labels(
            pred_paths=head_output,
            idx2label=self.id2label,
            pad_label='O',
            word_ids_list=[m.word_ids for m in embedding.mapping]
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


def decode_token_labels(pred_paths,
                        word_ids_list,
                        idx2label,
                        pad_label="O"):
    """
    Convert CRF subword output → word-level spans only.
    Returns: List[List[(label, start, end)]]
    """
    outputs = []

    for pred_sub, word_ids in zip(pred_paths, word_ids_list):

        # 1. Extract unique word indices in order
        unique_word_ids = []
        for wid in word_ids:
            if wid is not None and (not unique_word_ids or unique_word_ids[-1] != wid):
                unique_word_ids.append(wid)

        # 2. Convert subword → word BIO tags
        pred_word_tags = []
        for wid in unique_word_ids:
            sub_positions = [i for i, w in enumerate(word_ids) if w == wid]
            if not sub_positions:
                pred_word_tags.append(pad_label)
            else:
                pred_id = pred_sub[sub_positions[0]]  # first subword
                pred_word_tags.append(idx2label[pred_id])

        # 3. Return only spans
        spans = bio_to_spans(pred_word_tags)
        outputs.append(spans)

    return outputs
