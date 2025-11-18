import logging
import os

has_initialized = False


def initialize_logger():
    global has_initialized
    if has_initialized:
        return

    has_initialized = True
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    for key, value in os.environ.items():
        if key.startswith("logger_"):
            logging.getLogger(key[len("logger_"):].replace("__", ".")).setLevel(value)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
