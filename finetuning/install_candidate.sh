#!/usr/bin/env bash
# Load a fine-tuned GGUF into Ollama next to the original model. Does not touch .env or the running app.
# Usage: bash finetuning/install_candidate.sh ~/Downloads/jai-gguf/unsloth.Q4_K_M.gguf [jai-candidate]
set -euo pipefail
gguf="${1:?Give the path to the downloaded .gguf file}"
name="${2:-jai-candidate}"
base="qwen2.5:7b-instruct"
[ -f "$gguf" ] || { echo "No such file: $gguf" >&2; exit 1; }
gguf="$(cd "$(dirname "$gguf")" && pwd)/$(basename "$gguf")"
dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
# Same chat template, stop tokens and parameters as the base model, so only the weights differ.
{ echo "FROM $gguf"
  ollama show "$base" --modelfile | awk 'started || !/^#/ {started=1} started && !/^FROM /'
  # No repeat_penalty: it stopped Arabic sentence loops but made some replies empty (tested 1.15/256 and
  # 1.1/64). Loops are handled in the app instead (clean_reply / salvage_reply in assistant_capabilities).
} > "$dir/Modelfile"
ollama create "$name" -f "$dir/Modelfile"
echo "Created Ollama model '$name'. The app still uses $base until JADWAI_LOCAL_MODEL is changed in .env."
