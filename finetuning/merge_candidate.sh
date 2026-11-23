#!/usr/bin/env bash
# Merge the trained LoRA adapter (jai-lora.zip from Colab) into Ollama's own qwen2.5:7b-instruct weights,
# quantize and load it as jai-candidate. Does not touch .env or the running app.
# Needs llama-quantize: run `bash finetuning/build_quantize.sh` once first. Peak disk use about 15 GB.
#
# Why the odd quantization: the training changes each weight by only ~0.5%, and the base weights sit
# exactly on their own quantization grid (Q4_K for most tensors, Q6_K for some). Re-quantizing to the
# same grid, or to one that contains it (Q4_K -> Q5_K), snaps most weights back and erases the training
# (measured with check_merge.py: 1-6% kept on the same grid, ~42% for Q4_K -> Q5_K).
# So base Q4_K tensors become Q6_K and base Q6_K tensors become Q5_K; both keep >90%.
# Usage: bash finetuning/merge_candidate.sh [~/Downloads/jai-lora.zip] [jai-candidate]
set -euo pipefail
cd "$(dirname "$0")"
zip="${1:-$HOME/Downloads/jai-lora.zip}"
name="${2:-jai-candidate}"
models="models"
py="$models/.convert-venv/bin/python"
quantize="$models/llama.cpp-src/build/bin/llama-quantize"
command -v llama-quantize >/dev/null && quantize="$(command -v llama-quantize)"
[ -x "$quantize" ] || { echo "llama-quantize not found: run 'bash finetuning/build_quantize.sh' first" >&2; exit 1; }

[ -f "$models/jai-lora/adapter_model.safetensors" ] || unzip -q -o "$zip" -d "$models"
base_blob="$(ollama show qwen2.5:7b-instruct --modelfile | awk '/^FROM \//{print $2; exit}')"
[ -f "$base_blob" ] || { echo "Could not find the qwen2.5:7b-instruct weights in Ollama" >&2; exit 1; }

q8="$models/jai-merged.Q8_0.gguf"
out="$models/jai-merged.Q6_K-Q5_K.gguf"
types="$models/tensor-types.txt"
"$py" - "$base_blob" > "$types" <<'EOF'
import sys, gguf
for t in gguf.GGUFReader(sys.argv[1]).tensors:
    if t.name.startswith('blk.') and t.tensor_type == gguf.GGMLQuantizationType.Q6_K:
        print('^' + t.name.replace('.', r'\.') + '$=q5_k')
EOF
"$py" merge_lora.py "$base_blob" "$models/jai-lora" "$q8" q8_0
"$quantize" --allow-requantize --tensor-type-file "$types" "$q8" "$out" Q6_K
rm -f "$q8"
bash install_candidate.sh "$out" "$name"
rm -f "$out"
"$py" check_merge.py "$name" "$models/jai-lora"
echo "Done: $name is in Ollama (it keeps its own copy)."
