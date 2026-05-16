uv run --no-project --index-strategy unsafe-best-match --with "transformers>=4.57.1" \
--with torch --with safetensors --with gguf  python convert_lora_to_gguf.py \
"$1" --base ./qwen_metadata --outtype f16  --outfile "$2"
# 
# uv run --no-project --index-strategy unsafe-best-match --with "transformers>=4.57.1" \
# --with torch --with safetensors --with gguf  python convert_lora_to_gguf.py \
# "$1"  --outtype f32 --base ./Llama-16bit  --outfile "$2"