import logging
import os
import sys

from uvicorn.logging import DefaultFormatter

from lang3s.utils.logger.async_handler import AsyncQueueHandler

_is_initialized = False


def __initialize_logging():
    global _is_initialized
    if _is_initialized:
        return
    _is_initialized = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("fastcoref.modeling").setLevel(logging.WARNING)


__existing_loggers = {}


def get_logger(name: str):
    __initialize_logging()

    logger = __existing_loggers.get(name, None)
    if logger:
        return logger

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers or []:
        logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = DefaultFormatter(
        fmt="%(levelprefix)s %(asctime)s | %(name)s | %(message)s",
        use_colors=True,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    async_handler = AsyncQueueHandler(handler)
    async_handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    level = os.environ.get(f"LOGGER_{name.replace('__', '.')}", None)
    if level:
        logger.setLevel(level.upper())

    __existing_loggers[name] = logger

    return logger
