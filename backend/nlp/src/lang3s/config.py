import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

load_dotenv(os.environ.get("LANG3S_BACKEND_ENV", "lang3s_backend.env"))


class Config:
    def __init__(self):
        #####################################################################################
        # TOPIC MODELLING OPTIONS
        #####################################################################################
        self.REDUCED_DIMENSIONS = 200
        self.FULL_EMBEDDING_THRESHOLD = 0.65

        #####################################################################################
        # NLP OPTIONS
        #####################################################################################
        self.USE_COREFERENCE = True

        #####################################################################################
        # EMBEDDING MODEL CONSTANTS
        #####################################################################################
        self.TOKEN_EMBEDDING_DIMENSION = 768
        self.SEMANTIC_EMBEDDING_DIMENSION = 384

    def _read_docker_secret(self, secret_name: str) -> Any:
        try:
            secret_path = f"/run/secrets/{secret_name}"
            if os.path.exists(secret_path):
                with open(secret_path, "r") as f:
                    return f.read().strip()
        except IOError:
            pass
        return None

    def _get_static(self, key: str, default: Any) -> Any:
        value = self._read_docker_secret(key)
        if value is not None:
            return value
        return os.environ.get(key, default)

    def get_config_value(self, key: str, default: Any) -> Any:
        # 1. Check Secret
        value = self._read_docker_secret(key)
        if value is not None:
            return value

        # 2. Check Database
        try:
            import lang3s.data.db.database as db
            from lang3s.data.db.models import ConfigurationTable

            with db.get_session() as session:
                # Using .get() is efficient for PK lookups
                db_record = session.query(ConfigurationTable).get(key)
                if db_record is not None:
                    return db_record.value
        except Exception:
            # Fallback if DB is not reachable or table doesn't exist
            pass

        # 3. Check Env
        return os.environ.get(key, default)

    #####################################################################################
    # PROXY  PORT
    #####################################################################################
    @property
    def PROXY_HOST(self) -> str:
        return self._get_static("PROXY_HOST", "http://localhost:8003")

    #####################################################################################
    # PYTHON SERVICES PORT
    #####################################################################################
    @property
    def FASTAPI_PORT(self) -> int:
        return int(self._get_static("FAST_API_PORT", 23000))

    @property
    def FAST_API_ANALYTICS_PORT(self) -> int:
        return int(self._get_static("FAST_API_ANALYTICS_PORT", 23001))

    @property
    def LOCAL_LLM_PORT(self) -> int:
        return int(self._get_static("LOCAL_LLM_PORT", 23002))

    #####################################################################################

    #####################################################################################
    # NODEJS BACKEND AND SYSTEM KEY
    #####################################################################################
    @property
    def NODEJS_HOST(self) -> str:
        return self._get_static("NODEJS_HOST", "http://localhost:3000")

    @property
    def SYSTEM_API_KEY(self) -> str:
        return self._get_static("SYSTEM_API_KEY", "456789")

    #####################################################################################

    #####################################################################################
    # POSTGRES
    #####################################################################################
    @property
    def DB_PASSWORD(self) -> str:
        return self._get_static("POSTGRES_PASSWORD", "abba")

    @property
    def DB_USER(self) -> str:
        return self._get_static("POSTGRES_USER", "admin")

    @property
    def DB_HOST(self) -> str:
        return self._get_static("POSTGRES_HOST", "lang3s_database")

    @property
    def DB_PORT(self) -> int:
        return int(self._get_static("POSTGRES_PORT", 5432))

    @property
    def DB_URL(self) -> str:
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/lang3s"

    #####################################################################################

    #####################################################################################
    # REDIS
    #####################################################################################
    @property
    def REDIS_HOST(self) -> str:
        return self._get_static("REDIS_HOST", "lang3s_redis")

    @property
    def REDIS_PORT(self) -> int:
        return int(self._get_static("REDIS_PORT", 6379))

    @property
    def REDIS_DB(self) -> int:
        return int(self._get_static("REDIS_DB", 0))

    #####################################################################################

    #####################################################################################
    # FILE STORE
    #####################################################################################
    @property
    def FILESTORE_ROOT(self) -> str:
        return self._get_static("FILESTORE_ROOT", "/filestore")

    @property
    def MODELS_DIR(self) -> str:
        return self._get_static("MODELS_DIR", f"{self.FILESTORE_ROOT}/models")

    @property
    def ADAPTERS_DIR(self) -> str:
        return os.path.join(self.MODELS_DIR, "adapters")

    @property
    def ADAPTER_CONFIG_FILE(self) -> str:
        return os.path.join(self.ADAPTERS_DIR, "adapters.json")

    #####################################################################################

    #####################################################################################
    # EMBEDDING MODEL
    #####################################################################################
    @property
    def EMBEDDING_MODEL(self) -> str:
        return self._get_static(
            "EMBEDDING_MODEL", f"{self.FILESTORE_ROOT}/finetuned_xlm_roberta"
        )

    #####################################################################################
    # LLM SERVER
    #####################################################################################
    @property
    def LLM_HOST(self) -> str:
        return self.get_config_value("LLM_HOST", "http://localhost:1234")

    @property
    def LLM_MODEL(self) -> str:
        return self.get_config_value("LLM_MODEL", "qwen/qwen3-4b-2507")

    @property
    def LLM_API_KEY(self) -> str:
        return self.get_config_value("LLM_API_KEY", "")

    @property
    def LLM_NATIVE_TOOL_SUPPORT(self) -> bool:
        val = self.get_config_value("LLM_NATIVE_TOOL_SUPPORT", True)
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_SUPPORTS_SYSTEM_PROMPT(self) -> bool:
        val = self.get_config_value("LLM_SUPPORTS_SYSTEM_PROMPT", True)
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_SUPPORTS_STRUCTURED_OUTPUT(self) -> bool:
        val = self.get_config_value("LLM_SUPPORTS_STRUCTURED_OUTPUT", True)
        return str(val).lower() == "true" if isinstance(val, str) else bool(val)

    @property
    def LLM_CONTEXT_WINDOW(self) -> int:
        return int(self.get_config_value("LLM_CONTEXT_WINDOW", 8000))

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
    # LocalLLM PARAMETERS
    #####################################################################################

    @property
    def LOCAL_LLM_DEVICE(self) -> str:
        return self._get_static("LOCAL_LLM_DEVICE", "gpu")

    #####################################################################################

    def _get_best_device(self, is_inference: bool = False) -> str:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        elif not is_inference and torch.backends.mps.is_available():
            return "mps"
        return "cpu"


# Instantiate as a singleton
config = Config()
