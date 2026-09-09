import pytest

from lang3s.llm.local_models import (
    DEFAULT_LOCAL_MODEL,
    AdapterSpec,
    ModelSpec,
    get_local_model,
)
from lang3s.llm.lora_client import LoRaClient


def test_default_model_maps_friendly_adapter_name_to_llama_slot() -> None:
    model = get_local_model(DEFAULT_LOCAL_MODEL)

    assert model.filename == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    assert model.adapter_id("claim") == 0
    assert model.adapter("claim").filename == "claim_extraction.gguf"


def test_adapter_ids_follow_the_declared_order() -> None:
    model = ModelSpec(
        name="test-model",
        filename="test.gguf",
        adapters=(
            AdapterSpec(name="claim", filename="claim.gguf"),
            AdapterSpec(name="summary", filename="summary.gguf"),
        ),
    )

    assert model.adapter_id("claim") == 0
    assert model.adapter_id("summary") == 1


def test_unknown_adapter_is_rejected() -> None:
    with pytest.raises(ValueError, match="not registered"):
        get_local_model().adapter_id("missing")


def test_model_validation_requires_base_model_and_all_adapters(tmp_path) -> None:
    model = get_local_model()
    (tmp_path / model.filename).touch()
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / model.adapter("claim").filename).touch()

    model.validate_files(tmp_path)

    (adapters_dir / model.adapter("claim").filename).unlink()
    with pytest.raises(FileNotFoundError, match="claim_extraction.gguf"):
        model.validate_files(tmp_path)


def test_client_uses_the_model_scoped_adapter_slot() -> None:
    client = LoRaClient()

    request_body = client._extend_extra_body({}, "claim")

    assert request_body["lora"] == [{"id": 0, "scale": 1.0}]
