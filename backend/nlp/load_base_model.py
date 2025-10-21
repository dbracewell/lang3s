from transformers import (
    AutoTokenizer,
    AutoModel,
)

BASE_MODEL = "FacebookAI/xlm-roberta-base"
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModel.from_pretrained(BASE_MODEL)
