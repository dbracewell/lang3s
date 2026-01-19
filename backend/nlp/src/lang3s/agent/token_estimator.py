from transformers import AutoTokenizer


def _resolve_tokenizer(model_id: str):
    mid = model_id.lower()

    if "qwen" in mid:
        return "Qwen/Qwen2.5-7B-Instruct"

    if "llama" in mid or "llama3" in mid:
        return "meta-llama/Llama-3.1-8B-Instruct"

    if "mistral" in mid:
        return "mistralai/Mistral-7B-Instruct-v0.3"

    if "phi" in mid:
        return "microsoft/Phi-3-mini-128k-instruct"

    if "gemma" in mid:
        return "google/gemma-2-9b-it"

    return "meta-llama/Llama-3.1-8B-Instruct"


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
