import os.path
import threading
from ctypes import c_void_p
from typing import Any, Literal, Type, TypeVar, cast, overload

import instructor
import llama_cpp
from llama_cpp import Llama
from pydantic import BaseModel

from lang3s import config
from lang3s.llm import Message

MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
adapters = {"claim": "claim_extraction.gguf"}


T = TypeVar("T", bound=BaseModel)


class ClaimResult(BaseModel):
    claim: str


class LocalLLM:
    def __init__(
        self,
        n_ctx: int = 8_000,
        n_batch: int = 1024,
        chat_format: Literal[
            "qwen", "chatml", "chatml-function-calling"
        ] = "chatml-function-calling",
    ) -> None:
        self.llm_lock = threading.Lock()
        self.root = os.path.join(config.MODELS_DIR, "locallm")
        self.llm = Llama(
            model_path=os.path.join(self.root, MODEL_NAME),
            n_gpu_layers=0 if config.LOCAL_LLM_DEVICE.lower() == "cpu" else -1,
            n_ctx=n_ctx,
            verbose=False,
            n_batch=n_batch,
            chat_format=chat_format,
        )
        self.adapter_models: dict[str, c_void_p] = {}
        for k, v in adapters.items():
            self.adapter_models[k] = llama_cpp.llama_adapter_lora_init(  # type:ignore
                self.llm.model, os.path.join(self.root, "adapters", v).encode("utf-8")
            )
        self.client = instructor.patch(
            create=self.llm.create_chat_completion_openai_v1,
            mode=instructor.Mode.JSON,
        )

    @overload
    def generate(
        self,
        messages: list[Message],
        response_model: Type[T],
        adapter_name: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> T: ...

    @overload
    def generate(
        self,
        messages: list[Message],
        response_model=None,
        adapter_name: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> str: ...

    def generate(
        self,
        messages: list[Message],
        adapter_name: str | None = None,
        response_model: Type[T] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> str | T:
        print(f"Processing prompt on {os.getpid()}")
        with self.llm_lock:
            adapter = self.adapter_models.get(adapter_name) if adapter_name else None
            if adapter is not None:
                llama_cpp.llama_set_adapter_lora(self.llm.ctx, adapter, 1.0)

            try:
                if tools:
                    print("GENERATING")
                    chat_response = self.llm.create_chat_completion_openai_v1(
                        messages=[m.to_dict() for m in messages],  # type: ignore
                        tool_choice=tool_choice,
                        tools=tools,
                        **kwargs,
                    )
                    print("FINISHED")
                    message = chat_response.choices[0].message
                    if message.tool_calls is not None:
                        return message.tool_calls
                    if message.function_call is not None:
                        return message.function_call
                    return message.content

                chat_response = self.client(
                    messages=[m.to_dict() for m in messages],
                    response_model=response_model,
                    max_retries=2,
                    **kwargs,
                )
                if response_model:
                    return chat_response

                return chat_response.choices[0].message.content

            finally:
                if adapter is not None:
                    llama_cpp.llama_set_adapter_lora(self.llm.ctx, adapter, 0.0)


_localLLM: LocalLLM | None = None
_lock = threading.Lock()


def get_local_llm() -> LocalLLM:
    global _localLLM
    global _lock
    with _lock:
        if _localLLM is None:
            _localLLM = LocalLLM()
    return cast(LocalLLM, _localLLM)
