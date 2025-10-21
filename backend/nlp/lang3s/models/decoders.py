import torch
from typing import Dict, List

from transformers import PreTrainedTokenizerFast

from lang3s.config import BASE_ADAPTER_MODEL


def decode_tokens(
    input_ids: List[List[int]] | List[int], tok: PreTrainedTokenizerFast
) -> List[str]:
    if "roberta" in BASE_ADAPTER_MODEL.lower():
        return __decode_tokens_roberta(input_ids, tok)
    else:
        return __decode_tokens_bert(input_ids, tok)


def __decode_tokens_roberta(
    input_ids: List[List[int]], tok: PreTrainedTokenizerFast
) -> List[str]:
    original_tokens = []
    for sub_list in input_ids:
        tokens = tok.convert_ids_to_tokens(sub_list)
        buffer = ""
        for i in range(len(tokens)):
            token = tokens[i]
            if token == "<s>":
                continue
            if token == "</s>":
                if buffer != "":
                    original_tokens.append(buffer)
                    buffer = ""
                continue

            if token.startswith("Ġ"):
                buffer += token[1:]
            else:
                buffer += token

        if len(buffer) > 0:
            original_tokens.append(buffer)
    return original_tokens


def __decode_tokens_bert(
    input_ids: List[int], tok: PreTrainedTokenizerFast
) -> List[str]:
    tokens = tok.convert_ids_to_tokens(input_ids)
    original_tokens = []
    buffer = ""
    for i in range(len(tokens)):
        token = tokens[i]
        next_token = tokens[i + 1] if i + 1 < len(tokens) else ""

        if token == "[CLS]" or token == "[SEP]" or token == "[PAD]" or token == "[UNK]":
            continue

        if token.startswith("##"):
            buffer += token[2:]
        elif next_token.startswith("##"):
            buffer += token
        else:
            if len(buffer) > 0:
                original_tokens.append(buffer)
            original_tokens.append(token)
            buffer = ""

    if len(buffer) > 0:
        original_tokens.append(buffer)
    return original_tokens


def decode_labels(
    preds: torch.Tensor, tok: PreTrainedTokenizerFast, id2labels: Dict[int, str]
) -> List[str]:
    all_predictions = []
    for i, input_ids in enumerate(tok["input_ids"]):
        word_ids = tok.word_ids(batch_index=i)
        cur_preds, prev_word_idx = [], None
        for idx, word_idx in enumerate(word_ids):
            if word_idx is None or word_idx == prev_word_idx:
                continue
            cur_preds.append(id2labels[preds[i, idx].item()])
            prev_word_idx = word_idx
        all_predictions.append(cur_preds)
    return all_predictions
