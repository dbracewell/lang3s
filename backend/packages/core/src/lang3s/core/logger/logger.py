import importlib.util
import logging
import logging.config
import os
import warnings

try:
    import transformers

    transformers.logging.set_verbosity_error()
except ImportError:
    pass


if importlib.util.find_spec("uvicorn") is not None:
    DEFAULT_FORMATTER = {
        "()": "uvicorn.logging.DefaultFormatter",
        "fmt": "%(levelprefix)s %(asctime)s | %(name)s | %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
        "use_colors": False,
    }
else:
    DEFAULT_FORMATTER = {
        "format": "%(levelname)s %(asctime)s | %(name)s | %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }


_is_initialized = False
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default_formatter": DEFAULT_FORMATTER,
    },
    "handlers": {
        "stream": {
            "()": "lang3s.core.logger.async_handler.AsyncQueueHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["stream"],
            "level": "INFO",
        },
    },
}

LOGGING_FILE = os.environ.get("LOGGER_FILE", None)
if LOGGING_FILE:
    LOGGING_CONFIG["loggers"][""]["handlers"].append("file")
    LOGGING_CONFIG["handlers"]["file"] = {
        "class": "logging.FileHandler",
        "filename": LOGGING_FILE or "",
        "formatter": "uvicorn_file",
    }


def __initialize_logging():
    global _is_initialized
    if _is_initialized:
        return
    _is_initialized = True
    logging.config.dictConfig(LOGGING_CONFIG)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("fastcoref.modeling").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("fastcoref").setLevel(logging.ERROR)
    logging.getLogger("gliner").setLevel(logging.ERROR)
    logging.getLogger("numexpr.utils").setLevel(logging.ERROR)


__existing_loggers = {}


def get_logger(name: str):
    __initialize_logging()

    logger = __existing_loggers.get(name, None)
    if logger:
        return logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    level = os.environ.get(f"LOGGER_{name.replace('__', '.')}", None)
    if level:
        logger.setLevel(level.upper())

    __existing_loggers[name] = logger

    return logger
