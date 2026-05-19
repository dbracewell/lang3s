from transformers import AutoTokenizer

from .messages import Message, format_messages_for_model


def _resolve_tokenizer(model_id: str):
    mid = model_id.lower()

    if "qwen" in mid:
        return "Qwen/Qwen2.5-7B-Instruct"

    if "mistral" in mid:
        return "mistralai/Mistral-7B-Instruct-v0.3"

    if "phi" in mid:
        return "microsoft/Phi-3-mini-128k-instruct"

    return "openai-community/openai-gpt"


_cache = {}


def _get_tokenizer(model_name: str):
    tokenizer_name = _resolve_tokenizer(model_name)
    if not tokenizer_name in _cache:
        _cache[tokenizer_name] = AutoTokenizer.from_pretrained(tokenizer_name)
    return _cache[tokenizer_name]


def count_tokens(model_name: str, content: str | None) -> int:
    tokenizer = _get_tokenizer(model_name)
    return len(tokenizer(content)["input_ids"]) if content else 0


def estimate_tokens(model_name: str, messages: list[Message]) -> int:
    tokenizer = _get_tokenizer(model_name)
    total_tokens = 0
    for msg in format_messages_for_model(messages):
        if "content" in msg:
            total_tokens += len(tokenizer(msg["content"])["input_ids"])
    return total_tokens


class TokenEstimator:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(
            _resolve_tokenizer(
                model_id=model_name,
            )
        )

    def count_messages(self, messages) -> int:
        chat = []
        for m in messages:
            chat.append({"role": m["role"], "content": m["content"]})
        encoded = self.tokenizer.apply_chat_template(
            chat, tokenize=True, add_generation_prompt=False
        )
        return len(encoded)
