import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

for key, value in os.environ.items():
    if key.startswith("logger."):
        logging.getLogger(key[len("logger."):]).setLevel(value)
