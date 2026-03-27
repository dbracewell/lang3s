import os.path
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Type, TypeVar

import instructor
import llama_cpp
from llama_cpp import Llama
from pydantic import BaseModel

from lang3s import config
from lang3s.nlp.shared_types import Document

MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"  # "qwen2.5-1.5b-instruct-q8_0.gguf"
adapters = {"claim": "claim_extraction.gguf"}


def _create_claim_prompt(context: list[str], sentence: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a precise information extraction engine and an expert at extracting factual claims from text.",
        },
        {
            "role": "user",
            "content": f"Extract claim from: {' '.join(context)} {sentence}",
        },
    ]


T = TypeVar("T", bound=BaseModel)


class ClaimResult(BaseModel):
    claim: str


class LocalLLM:
    def __init__(self):
        self.llm_lock = threading.Lock()
        self.root = os.path.join(config.MODELS_DIR, "locallm")
        self.llm = Llama(
            model_path=os.path.join(self.root, MODEL_NAME),
            n_gpu_layers=0 if config.LOCAL_LLM_DEVICE.lower() == "cpu" else -1,
            n_ctx=2048,
            verbose=False,
            n_batch=1024,
            chat_format="chatml",
        )
        self.adapter_models = {}
        for k, v in adapters.items():
            self.adapter_models[k] = llama_cpp.llama_adapter_lora_init(
                self.llm.model, os.path.join(self.root, "adapters", v).encode("utf-8")
            )
        self.client = instructor.patch(
            create=self.llm.create_chat_completion_openai_v1,
            mode=instructor.Mode.JSON,
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens=256,
        max_workers=4,
        adapter_name: str | None = None,
        response_model: Type[T] | None = None,
        **kwargs,
    ) -> list[str | T]:

        adapter = self.adapter_models.get(adapter_name)
        if adapter is not None:
            llama_cpp.llama_set_adapter_lora(self.llm.ctx, adapter, 1.0)

        def process(message):
            with self.llm_lock:
                chat_response = self.client(
                    messages=message,
                    max_tokens=max_tokens,
                    response_model=response_model,
                    max_retries=2,
                    **kwargs,
                )
                if response_model:
                    return chat_response

                return chat_response.choices[0].message.content

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process, messages))

        if adapter is not None:
            llama_cpp.llama_set_adapter_lora(self.llm.ctx, adapter, 0.0)

        return results

    def extract_claims(self, document: Document) -> list[str]:
        if not document.text:
            return []
        sentences = [s.text_with_coref() for s in document.text.sentences]
        messages = []
        for i, sentence in enumerate(sentences):
            messages.append(
                _create_claim_prompt(sentences[max(0, i - 2) : i], sentence)
            )
        return self.generate(
            messages,
            max_tokens=75,
            adapter_name="claim",
            temperature=0.0,
            seed=42,
        )


_localLLM: LocalLLM | None = None


def get_local_llm() -> LocalLLM:
    global _localLLM
    if _localLLM is None:
        _localLLM = LocalLLM()
    return _localLLM
