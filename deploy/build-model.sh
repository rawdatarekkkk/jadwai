#!/usr/bin/env bash
# Rebuild jai-candidate-v4 on the server from the 150 MB LoRA adapter instead of uploading 6 GB:
# pull the same base model from Ollama, build llama-quantize, merge exactly as on the Mac.
# Run on the server after server-setup.sh: bash ~/jadwai/deploy/build-model.sh
set -euo pipefail
cd "$(dirname "$0")/../finetuning"
export OLLAMA_HOST=127.0.0.1:11434
ollama list | grep -q '^jai-candidate-v4' && { echo "jai-candidate-v4 already installed"; exit 0; }
ollama pull qwen2.5:7b-instruct
# Same tool versions as the Mac that built v4 (gguf 0.19.0; llama.cpp source copied by push.sh).
[ -x models/.convert-venv/bin/python ] || { python3 -m venv models/.convert-venv; models/.convert-venv/bin/pip install -q gguf==0.19.0 numpy==2.5.5; }
bash build_quantize.sh
rm -rf models/jai-lora
bash merge_candidate.sh models/jai-lora-v4.zip jai-candidate-v4
# Leave one of the four cores to the website while the model is answering.
ollama show jai-candidate-v4 --modelfile | grep -v '^PARAMETER num_thread' > /tmp/jai-v4.Modelfile
echo 'PARAMETER num_thread 3' >> /tmp/jai-v4.Modelfile
ollama create jai-candidate-v4 -f /tmp/jai-v4.Modelfile
ollama list
