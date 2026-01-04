import requests
from transformers import AutoTokenizer

from lang3s import config


def _resolve_tokenizer(model_id: str):
    try:
        resp = requests.get(f"{config.LLM_HOST}/v1/models").json()
        for m in resp.get("data", []):
            if m["id"] == model_id:
                details = m.get("details", {})
                family = (
                    details.get("family")
                    or m.get("metadata", {}).get("model_type")
                    or ""
                ).lower()
                if "qwen" in family:
                    return "Qwen/Qwen2.5-7B-Instruct"
                if "llama" in family:
                    return "meta-llama/Llama-3.1-8B-Instruct"
                if "mistral" in family:
                    return "mistralai/Mistral-7B-Instruct-v0.3"
                if "phi" in family:
                    return "microsoft/Phi-3-mini-128k-instruct"
                if "gemma" in family:
                    return "google/gemma-2-9b-it"
    except Exception:
        pass

        # --- 2. Fallback: infer family from model_id pattern ---
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

    return "Qwen/Qwen2.5-7B-Instruct"
    # raise RuntimeError(f"Cannot determine tokenizer family for {model_id}")


class TokenEstimator:
    def __init__(self, model_name: str):
        self.tokenizer = AutoTokenizer.from_pretrained(_resolve_tokenizer(model_name))

    def count_messages(self, messages) -> int:
        # Convert OpenAI-style messages into model-native chat format
        chat = []
        for m in messages:
            chat.append({"role": m["role"], "content": m["content"]})

        # Use apply_chat_template() because this builds the *actual* tokens used
        encoded = self.tokenizer.apply_chat_template(
            chat, tokenize=True, add_generation_prompt=False
        )
        return len(encoded)
