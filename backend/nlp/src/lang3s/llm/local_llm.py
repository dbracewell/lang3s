import os.path
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Type, TypeVar

import instructor
from llama_cpp import Llama
from pydantic import BaseModel

from lang3s import config
from lang3s.nlp.shared_types import Document

MODEL_NAME = "claimllm.gguf"


def _create_claim_prompt(context: list[str], sentence: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a precise information extraction engine.",
        },
        {
            "role": "user",
            "content": f"Extract claim from: {' '.join(context)} {sentence}",
        },
    ]


T = TypeVar("T", bound=BaseModel)


class LocalLLM:
    def __init__(self):
        self.llm_lock = threading.Lock()
        self.llm = Llama(
            model_path=os.path.join(config.MODELS_DIR, MODEL_NAME),
            n_gpu_layers=0 if config.LOCAL_LLM_DEVICE.lower() == "cpu" else -1,
            n_ctx=2048,
            verbose=False,
            n_batch=1024,
            chat_format="chatml",
        )
        self.client = instructor.patch(
            create=self.llm.create_chat_completion_openai_v1,
            mode=instructor.Mode.JSON,
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        batch_size=10,
        max_tokens=256,
        max_workers=4,
        response_model: Type[T] | None = None,
        **kwargs,
    ) -> list[str | T]:
        def process(message):
            with self.llm_lock:
                chat_response = self.client(
                    messages=message,
                    max_tokens=max_tokens,
                    temperature=0.0,
                    response_model=response_model,
                    max_retries=2,
                    **kwargs,
                )

                if response_model:
                    return chat_response

                return chat_response.choices[0].message.content

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i in range(0, len(messages), batch_size):
                batch = messages[i : i + batch_size]
                batch_results = list(executor.map(process, batch))
                results.extend(batch_results)
        return results

    def extract_claims(self, document: Document, batch_size=10) -> list[str]:
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
            batch_size=batch_size,
            max_tokens=75,
        )
