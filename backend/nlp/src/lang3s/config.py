import os
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.environ.get("LANG3S_BACKEND_ENV", "lang3s_backend.env"))


def _get_best_device(is_inference: bool = False) -> str:
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda").type
    elif not is_inference and torch.backends.mps.is_available():
        # Don't use mps for inference, it has a lot of memory problems
        # where mps won't release memory not needed causing giant
        # memory bloat
        return torch.device("mps").type
    else:
        return torch.device("cpu").type


def _read_docker_secret(secret_name, default: Any) -> Any:
    try:
        secret_path = f"/run/secrets/{secret_name}"
        if os.path.exists(secret_path):
            with open(secret_path, "r") as f:
                return f.read().strip()
        return default
    except IOError as e:
        return default


def _get_config_value(key: str, default: Any) -> Any:
    return os.environ.get(key, _read_docker_secret(key, default))


#####################################################################################
# PYTHON SERVICES PORT
#####################################################################################
FASTAPI_PORT: int = int(_get_config_value("FAST_API_PORT", "8003"))

#####################################################################################
# NODEJS BACKEND AND SYSTEM KEY
#####################################################################################
NODEJS_HOST: str = _get_config_value("NODEJS_HOST", "http://localhost:3000")
SYSTEM_API_KEY: str = _get_config_value("SYSTEM_API_KEY", "456789")

#####################################################################################
# POSTGRES
#####################################################################################
DB_PASSWORD: str = _get_config_value("POSTGRES_PASSWORD", "abba")
DB_USER: str = _get_config_value("POSTGRES_USER", "admin")
DB_HOST: str = _get_config_value("POSTGRES_HOST", "lang3s_database")
DB_PORT: int = int(_get_config_value("POSTGRES_PORT", 5432))
DB_URL: str = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/lang3s"

#####################################################################################
# REDIS
#####################################################################################
REDIS_HOST: str = _get_config_value("REDIS_HOST", "lang3s_redis")  # "100.118.226.19")
REDIS_PORT: int = int(_get_config_value("REDIS_PORT", 6379))
REDIS_DB: int = int(_get_config_value("REDIS_DB", 0))

#####################################################################################
# LLM SERVER
#####################################################################################
LLM_HOST: str = _get_config_value("LLM_HOST", "http://localhost:1234")
LLM_MODEL: str = _get_config_value("LLM_MODEL", "qwen/qwen3-4b-2507")
LLM_API_KEY: str = _get_config_value("LLM_API_KEY", "")

#####################################################################################
# NLP OPTIONS
#####################################################################################
USE_COREFERENCE: bool = True

#####################################################################################
# TOPIC MODELLING OPTIONS
#####################################################################################
REDUCED_DIMENSIONS: int = 200
FULL_EMBEDDING_THRESHOLD: float = 0.65

#####################################################################################
# FILE STORE
#####################################################################################
FILESTORE_ROOT: str = _get_config_value("FILESTORE_ROOT", "/filestore")

#####################################################################################
# MODELS
#####################################################################################
EMBEDDING_MODEL: str = _get_config_value(
    "XLM_ROBERTA", f"{FILESTORE_ROOT}/finetuned_xlm_roberta"
)
TOKEN_EMBEDDING_DIMENSION: int = 768
SEMANTIC_EMBEDDING_DIMENSION: int = 384

MODELS_DIR: str = _get_config_value("MODELS_DIR", f"{FILESTORE_ROOT}/models")
ADAPTERS_DIR: str = os.path.join(MODELS_DIR, "adapters")
ADAPTER_CONFIG_FILE: str = os.path.join(ADAPTERS_DIR, "adapters.json")

#####################################################################################
# TRAINING AND INFERENCE PARAMETERS
#####################################################################################
TRAINING_DEVICE: str = _get_config_value("TRAINING_DEVICE", _get_best_device())
INFERENCE_DEVICE: str = _get_config_value(
    "INFERENCE_DEVICE", _get_best_device(is_inference=True)
)
INFERENCE_BATCH_SIZE: int = int(_get_config_value("INFERENCE_BATCH_SIZE", 32))
