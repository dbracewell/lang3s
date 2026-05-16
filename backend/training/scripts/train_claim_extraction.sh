#!/usr/bin/env bash

uv run --project nlp/pyproject.toml \
python -m training.localllm.train_lora \
--json_path ~/prj/data/document_claim_extraction_v3.jsonl \
--epochs 5