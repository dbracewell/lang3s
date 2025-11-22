import logging
import os

from .async_handler import AsyncQueueHandler
from .formatter import ColoredFormatter

_initialized = False


def initialize_logging(
    default_level="INFO",
    enable_colors=True,
    root_name=None,
):
    global _initialized
    if _initialized:
        return
    _initialized = True

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(use_colors=enable_colors))
    async_handler = AsyncQueueHandler(console_handler)

    logging.basicConfig(
        level=getattr(logging, default_level),
        handlers=[async_handler],
        force=True,
    )

    root = logging.getLogger(root_name) if root_name else logging.getLogger()

    for key, value in os.environ.items():
        if key.startswith("LOGGER_"):
            name = key[len("LOGGER_"):].replace("__", ".")
            level = value.upper()
            logging.getLogger(name).setLevel(level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
