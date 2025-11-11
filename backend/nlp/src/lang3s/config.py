import os
from typing import Any

import torch

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUNBUFFERED"] = "1"


def get_best_device():
  if torch.cuda.is_available():
    return torch.device("cuda").type
  elif torch.backends.mps.is_available():
    return torch.device("mps").type
  else:
    return torch.device("cpu").type


XLM_ROBERTA = "xlm-roberta-base"
GTE_MODEL = "Alibaba-NLP/gte-multilingual-base"

__DEFAULT_EMBEDDING_MODEL = GTE_MODEL
__DEFAULT_ADAPTER_MODEL = XLM_ROBERTA
__DEFAULT_MODELS_DIR = "/app"
__DEFAULT_DOCUMENTS_DIR = "/Users/ik/prj/Lang3s/documents"


def __get_environment_var(name: str, default: Any) -> Any:
  if name in os.environ:
    return os.environ[name]
  return default


PYTHON_BACKEND = __get_environment_var(
  "PYTHON_BACKEND", "http://localhost:8003"
)
SYSTEM_API_KEY = __get_environment_var("SYSTEM_API_KEY", "456789")
BACKEND_HOST = __get_environment_var("BACKEND_HOST", "http://localhost:3001")

DB_PASSWORD = __get_environment_var("POSTGRES_PASSWORD", "abba")
DB_USER = __get_environment_var("POSTGRES_USER", "admin")
DB_HOST = __get_environment_var("POSTGRES_HOST", "localhost")
DB_PORT = int(__get_environment_var("POSTGRES_PORT", 5432))

REDIS_HOST = __get_environment_var("REDIS_HOST", "localhost")
REDIS_PORT = int(__get_environment_var("REDIS_PORT", 6379))
REDIS_DB = int(__get_environment_var("REDIS_DB", 0))

LLM_HOST = __get_environment_var("LLM_HOST", "http://localhost:1234")
LLM_MODEL = __get_environment_var("LLM_MODEL", "google/gemma-3n-e4b")
LLM_API_KEY = __get_environment_var("LLM_API_KEY", "")

DEVICE: str = __get_environment_var("DEVICE", get_best_device())

BASE_ADAPTER_MODEL: str = __get_environment_var(
  "BASE_ADAPTER_MODEL", __DEFAULT_ADAPTER_MODEL
)
EMBEDDING_MODEL: str = __get_environment_var(
  "EMBEDDING_MODEL", __DEFAULT_EMBEDDING_MODEL
)

DOCUMENTS_DIR: str = __get_environment_var(
  "DOCUMENTS_DIR", __DEFAULT_DOCUMENTS_DIR
)

MODELS_DIR: str = __get_environment_var("MODELS_DIR", __DEFAULT_MODELS_DIR)
ADAPTERS_DIR: str = os.path.join(MODELS_DIR, "adapters")
ADAPTER_CONFIG_FILE: str = os.path.join(ADAPTERS_DIR, "adapters.json")
INFERENCE_BATCH_SIZE: int = int(
  __get_environment_var("INFERENCE_BATCH_SIZE", 32)
)

BIO_TRAIN_BATCH_SIZE = 32
BIO_TRAIN_NUM_EPOCHS = 20
BIO_TRAIN_LR = 1e-4
BIO_TRAIN_LABEL_ALL_TOKENS = False
