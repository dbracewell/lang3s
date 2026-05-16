import os
from pathlib import Path

DATA_ROOT = Path(os.path.expanduser("~/prj/data/coref_dataset"))

WIKICOREF_DIR = DATA_ROOT / "wikicoref"
GUM_DIR = DATA_ROOT / "ontogum/conll"
SYNTHETIC_DATA = DATA_ROOT / "coref_data.jsonl"

TRAINING_DATA_DIR = DATA_ROOT / "document_coref.pt"
