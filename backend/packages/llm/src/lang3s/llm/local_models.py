from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdapterSpec:
    """A friendly adapter name and the GGUF artifact loaded by llama-server."""

    name: str
    filename: str


@dataclass(frozen=True)
class ModelSpec:
    """A local base model and its ordered llama-server adapter slots."""

    name: str
    filename: str
    adapters: tuple[AdapterSpec, ...]

    def __post_init__(self) -> None:
        adapter_names = [adapter.name for adapter in self.adapters]
        adapter_files = [adapter.filename for adapter in self.adapters]
        if len(adapter_names) != len(set(adapter_names)):
            raise ValueError(f"Duplicate adapter names for model {self.name!r}")
        if len(adapter_files) != len(set(adapter_files)):
            raise ValueError(f"Duplicate adapter files for model {self.name!r}")

    def adapter_id(self, adapter_name: str) -> int:
        """Return the llama-server slot ID for a friendly adapter name."""
        for index, adapter in enumerate(self.adapters):
            if adapter.name == adapter_name:
                return index
        raise ValueError(
            f"Adapter {adapter_name!r} is not registered for model {self.name!r}"
        )

    def adapter(self, adapter_name: str) -> AdapterSpec:
        return self.adapters[self.adapter_id(adapter_name)]

    def validate_files(self, model_directory: Path) -> None:
        """Ensure the base model and every registered adapter are present."""
        expected_files = [model_directory / self.filename]
        expected_files.extend(
            model_directory / "adapters" / adapter.filename
            for adapter in self.adapters
        )
        missing_files = [path for path in expected_files if not path.is_file()]
        if missing_files:
            missing = ", ".join(str(path) for path in missing_files)
            raise FileNotFoundError(
                f"Missing artifacts for local model {self.name!r}: {missing}"
            )


DEFAULT_LOCAL_MODEL = "qwen-2.5-1.5b"

# The order of each adapters tuple is the order passed to llama-server. Do not
# reorder existing entries: their indexes are the request-level LoRA slot IDs.
LOCAL_MODELS: dict[str, ModelSpec] = {
    DEFAULT_LOCAL_MODEL: ModelSpec(
        name=DEFAULT_LOCAL_MODEL,
        filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        adapters=(
            AdapterSpec(name="claim", filename="claim_extraction.gguf"),
        ),
    ),
}


def get_local_model(model_name: str = DEFAULT_LOCAL_MODEL) -> ModelSpec:
    try:
        return LOCAL_MODELS[model_name]
    except KeyError as exc:
        raise ValueError(f"Unknown local model {model_name!r}") from exc
