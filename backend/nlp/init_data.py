from gliner import GLiNER
from spacy_download import load_spacy
from transformers import AutoTokenizer

SPACY_MODELS = [
    "en_core_web_sm",
    "ja_core_news_sm",
    "es_core_news_sm",
]

TOKENIZER_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "microsoft/Phi-3-mini-128k-instruct",
    "openai-community/openai-gpt",
]

for model in SPACY_MODELS:
    load_spacy(model)

for tokenizer in TOKENIZER_MODELS:
    AutoTokenizer.from_pretrained(tokenizer)

GLiNER.from_pretrained(
    "knowledgator/gliner-bi-base-v2.0",
)
