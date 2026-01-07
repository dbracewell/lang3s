import logging
import os
import sys

from .async_handler import AsyncQueueHandler
from .formatter import ColoredFormatter

_initialized = False


def initialize_logging(
    default_level="INFO",
    enable_colors=True,
):
    global _initialized
    if _initialized:
        return
    _initialized = True

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter(use_colors=enable_colors))
    async_handler = AsyncQueueHandler(console_handler)
    async_handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    logging.basicConfig(
        level=getattr(logging, default_level),
        handlers=[async_handler],
        force=True,
    )

    for key, value in os.environ.items():
        if key.startswith("LOGGER_"):
            name = key[len("LOGGER_") :].replace("__", ".")
            level = value.upper()
            logging.getLogger(name).setLevel(level)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("fastcoref.modeling").setLevel(logging.WARNING)
