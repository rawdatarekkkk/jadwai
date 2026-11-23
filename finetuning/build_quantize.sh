#!/usr/bin/env bash
# Build only llama.cpp's llama-quantize tool (no Homebrew, no LLVM). Takes a few minutes on this Mac.
# Result: finetuning/models/llama.cpp-src/build/bin/llama-quantize
set -euo pipefail
cd "$(dirname "$0")/models"
[ -x .convert-venv/bin/python ] || { python3 -m venv .convert-venv; .convert-venv/bin/pip install -q gguf numpy; }
.convert-venv/bin/pip install -q cmake
if [ ! -f llama.cpp-src/CMakeLists.txt ]; then
  rm -rf llama.cpp-src
  git clone -q --depth 1 https://github.com/ggml-org/llama.cpp.git llama.cpp-src || {
    echo "git clone failed, trying the source archive instead"
    mkdir -p llama.cpp-src
    curl -fL --retry 5 --retry-all-errors https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/heads/master \
      | tar -xz --strip-components 1 -C llama.cpp-src
  }
fi
cd llama.cpp-src
../.convert-venv/bin/cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DGGML_METAL=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_EXAMPLES=OFF
../.convert-venv/bin/cmake --build build --target llama-quantize -j 8
ls -la build/bin/llama-quantize && echo "llama-quantize is ready"
