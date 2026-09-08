import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class Config:
    def __init__(self):
        load_dotenv()

        #####################################################################################
        # TOPIC MODELLING OPTIONS
        #####################################################################################
        self.REDUCED_DIMENSIONS: int = 200
        self.FULL_EMBEDDING_THRESHOLD: float = 0.65

        #####################################################################################
        # NLP OPTIONS
        #####################################################################################
        self.USE_COREFERENCE: bool = True

        #####################################################################################
        # EMBEDDING MODEL CONSTANTS
        #####################################################################################
        self.TOKEN_EMBEDDING_DIMENSION: int = 768
        self.SEMANTIC_EMBEDDING_DIMENSION: int = 384

    def _read_docker_secret(self, secret_name: str) -> Any:  # pyright: ignore[reportExplicitAny]
        try:
            secret_path = f"/run/secrets/{secret_name}"
            if os.path.exists(secret_path):
                with open(secret_path, "r") as f:
                    return f.read().strip()
        except IOError:
            pass
        return None

    def get_config_value(self, key: str, default: Any) -> Any:
        value = self._read_docker_secret(key)
        if value is not None:
            return value
        value = self._read_docker_secret(key.lower())
        if value is not None:
            return value
        return os.environ.get(key, default)

    @property
    def SYSTEM_KEY(self) -> str:
        value = self.get_config_value("SYSTEM_KEY", None)
        if value is None:
            raise RuntimeError("SYSTEM_KEY not set")
        return value

    #####################################################################################
    # PROXY  PORT
    #####################################################################################
    @property
    def PROXY_HOST(self) -> str:
        return self.get_config_value("PROXY_HOST", "http://lang3s_caddy:8003")

    #####################################################################################
    # PYTHON SERVICES PORT
    #####################################################################################
    @property
    def FASTAPI_PORT(self) -> int:
        return int(self.get_config_value("FAST_API_PORT", 23000))

    @property
    def FAST_API_ANALYTICS_PORT(self) -> int:
        return int(self.get_config_value("FAST_API_ANALYTICS_PORT", 23001))

    @property
    def LOCAL_LLM_PORT(self) -> int:
        return int(self.get_config_value("LOCAL_LLM_PORT", 23002))

    #####################################################################################

    #####################################################################################
    # NODEJS BACKEND AND SYSTEM KEY
    #####################################################################################
    @property
    def BETTER_AUTH_URL(self) -> str:
        return self.get_config_value("BETTER_AUTH_URL", "http://lang3s_frontend:3000")

    @property
    def JWT_ISSUER(self) -> str:
        return self.get_config_value("JWT_ISSUER", self.BETTER_AUTH_URL)

    @property
    def JWT_AUDIENCE(self) -> str:
        return self.get_config_value("JWT_AUDIENCE", self.BETTER_AUTH_URL)

    @property
    def JWKS_URL(self) -> str:
        return self.get_config_value(
            "JWKS_URL", f"{self.BETTER_AUTH_URL}/api/auth/jwks"
        )

    #####################################################################################

    #####################################################################################
    # POSTGRES
    #####################################################################################
    @property
    def DB_PASSWORD(self) -> str:
        return self.get_config_value("POSTGRES_PASSWORD", "abba")

    @property
    def DB_USER(self) -> str:
        return self.get_config_value("POSTGRES_USER", "admin")

    @property
    def DB_HOST(self) -> str:
        return self.get_config_value("POSTGRES_HOST", "lang3s_database")

    @property
    def DB_PORT(self) -> int:
        return int(self.get_config_value("POSTGRES_PORT", 5432))

    @property
    def DB_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/lang3s"

    #####################################################################################

    #####################################################################################
    # REDIS
    #####################################################################################
    @property
    def REDIS_HOST(self) -> str:
        return self.get_config_value("REDIS_HOST", "lang3s_redis")

    @property
    def REDIS_PORT(self) -> int:
        return int(self.get_config_value("REDIS_PORT", 6379))

    @property
    def REDIS_DB(self) -> int:
        return int(self.get_config_value("REDIS_DB", 0))

    #####################################################################################

    #####################################################################################
    # FILE STORE AND MODELS LOCATION
    #####################################################################################
    @property
    def FILESTORE_ROOT(self) -> Path:
        return Path(self.get_config_value("FILESTORE_ROOT", "/filestore"))

    @property
    def MODELS_DIR(self) -> Path:
        return self.FILESTORE_ROOT / self.get_config_value("MODELS_DIR", "models")

    @property
    def ADAPTERS_DIR(self) -> Path:
        return self.MODELS_DIR / "adapters"

    @property
    def ADAPTER_CONFIG_FILE(self) -> Path:
        return self.ADAPTERS_DIR / "adapters.json"

    @property
    def EMBEDDING_MODEL(self) -> str:
        return self.get_config_value("EMBEDDING_MODEL", f"{self.MODELS_DIR}/embedding")

    #####################################################################################

    #####################################################################################
    # LLM SERVER
    #####################################################################################
    @property
    def LLM_HOST(self) -> str:
        return self.get_config_value("LLM_HOST", "http://localhost:1234/v1")

    @property
    def LLM_MODEL(self) -> str:
        return self.get_config_value("LLM_MODEL", "qwen/qwen3-4b-2507")

    @property
    def LLM_API_KEY(self) -> str:
        return self.get_config_value("LLM_API_KEY", "no-key-given")

    @property
    def LLM_NATIVE_TOOL_SUPPORT(self) -> bool:
        val = self.get_config_value("LLM_NATIVE_TOOL_SUPPORT", "true")
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_SUPPORTS_SYSTEM_PROMPT(self) -> bool:
        val = self.get_config_value("LLM_SUPPORTS_SYSTEM_PROMPT", "true")
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_SUPPORTS_STRUCTURED_OUTPUT(self) -> bool:
        val = self.get_config_value("LLM_SUPPORTS_STRUCTURED_OUTPUT", "true")
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_CONTEXT_WINDOW(self) -> int:
        return int(self.get_config_value("LLM_CONTEXT_WINDOW", 32000))

    @property
    def LOCAL_LLM_DEVICE(self) -> str:
        return self.get_config_value("LOCAL_LLM_DEVICE", "gpu")

    #####################################################################################

    #####################################################################################
    # TRAINING AND INFERENCE PARAMETERS
    #####################################################################################
    @property
    def INFERENCE_BATCH_SIZE(self) -> int:
        return int(self.get_config_value("INFERENCE_BATCH_SIZE", 32))

    @property
    @lru_cache(maxsize=1)
    def TRAINING_DEVICE(self) -> str:
        # Default device is calculated only if not overridden in DB/Env
        default_dev = self._get_best_device(is_inference=False)
        return self.get_config_value("TRAINING_DEVICE", default_dev)

    @property
    @lru_cache(maxsize=1)
    def INFERENCE_DEVICE(self) -> str:
        default_dev = self._get_best_device(is_inference=True)
        return self.get_config_value("INFERENCE_DEVICE", default_dev)

    @property
    @lru_cache(maxsize=1)
    def NER_INFERENCE_DEVICE(self) -> str:
        default_dev = self._get_best_device(is_inference=True)
        return self.get_config_value("NER_INFERENCE_DEVICE", default_dev)

    #####################################################################################
    # NER PARAMETERS
    #####################################################################################

    @property
    @lru_cache(maxsize=1)
    def NER_CONFIDENCE_THRESHOLD(self) -> float:
        return self.get_config_value("NER_CONFIDENCE_THRESHOLD", 0.3)

    #####################################################################################

    def _get_best_device(self, is_inference: bool = False) -> str:
        try:
            import torch
        except ImportError:
            return "cpu"

        if is_inference:
            return "cpu"

        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"


config = Config()
