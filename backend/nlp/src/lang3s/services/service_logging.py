import logging
import sys

from uvicorn.logging import DefaultFormatter


def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s", use_colors=True)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
