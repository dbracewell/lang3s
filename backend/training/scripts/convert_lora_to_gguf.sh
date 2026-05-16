#!/usr/bin/env bash

# $1 = lora, $2 = base model $3 = output file
uv run --no-project --index-strategy unsafe-best-match --with "transformers>=4.57.1" \
--with torch --with safetensors --with gguf  python convert_lora_to_gguf.py \
"$1" --base "$2" --outtype f16  --outfile "$3"
