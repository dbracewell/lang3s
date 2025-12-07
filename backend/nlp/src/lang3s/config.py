import os

#####################################################################################
# PYTHON SERVICES PORT
#####################################################################################
FASTAPI_PORT = int(os.environ.get(
    "FAST_API_PORT", "8003"
))

#####################################################################################
# NODEJS BACKEND AND SYSTEM KEY
#####################################################################################
NODEJS_HOST = os.environ.get("BACKEND_HOST", "http://localhost:3001")
SYSTEM_API_KEY = os.environ.get("SYSTEM_API_KEY", "456789")

#####################################################################################
# POSTGRES
#####################################################################################
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "abba")
DB_USER = os.environ.get("POSTGRES_USER", "admin")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = int(os.environ.get("POSTGRES_PORT", 5432))
DB_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/lang3s"

#####################################################################################
# REDIS
#####################################################################################
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

#####################################################################################
# LLM SERVER
#####################################################################################
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:1234")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3-4b-2507")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

#####################################################################################
# EMBEDDING MODEL
#####################################################################################
XLM_ROBERTA = "xlm-roberta-base"
GTE_MODEL = "Alibaba-NLP/gte-multilingual-base"
MENTAL_HEALTH_ROBERTA = "mental/mental-roberta-base"
__DEFAULT_EMBEDDING_MODEL = XLM_ROBERTA
EMBEDDING_MODEL: str = os.environ.get(
    "EMBEDDING_MODEL", __DEFAULT_EMBEDDING_MODEL
)
EMBEDDING_DIMENSION = 768

#####################################################################################
# STORAGE DIRECTORIES
#####################################################################################
__DEFAULT_MODELS_DIR = "/app"
__DEFAULT_DOCUMENTS_DIR = "/Users/ik/prj/Lang3s/documents"
DOCUMENTS_DIR: str = os.environ.get(
    "DOCUMENTS_DIR", __DEFAULT_DOCUMENTS_DIR
)
MODELS_DIR: str = os.environ.get("MODELS_DIR", __DEFAULT_MODELS_DIR)
ADAPTERS_DIR: str = os.path.join(MODELS_DIR, "adapters")
ADAPTER_CONFIG_FILE: str = os.path.join(ADAPTERS_DIR, "adapters.json")


#####################################################################################
# TRAINING AND INFERENCE PARAMETERS
#####################################################################################
def get_best_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda").type
    elif torch.backends.mps.is_available():
        return torch.device("mps").type
    else:
        return torch.device("cpu").type


TRAINING_DEVICE: str = os.environ.get("TRAINING_DEVICE", get_best_device())
INFERENCE_DEVICE: str = os.environ.get("INFERENCE_DEVICE", get_best_device())
INFERENCE_BATCH_SIZE: int = int(
    os.environ.get("INFERENCE_BATCH_SIZE", 32)
)
