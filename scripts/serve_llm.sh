#!/usr/bin/env bash
# Serve Qwen3.5-9B (Q8_0 GGUF) + vision projector (mmproj F16) with llama.cpp on one V100 32 GB
# (sm_70; vLLM does not support it). Set MMPROJ= (empty) for text only.
# 8 parallel slots × 20k tokens; the KV cache stays small (only 8 of 32 layers use full attention).
#
#   scripts/serve_llm.sh            # then CLASSIFIER=local, LOCAL_LLM_URL=http://127.0.0.1:8080/v1
#
# llama.cpp v0.5.0 built with: cmake -B build -G Ninja -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 \
#   -DCMAKE_CUDA_COMPILER=/usr/local/cuda-12.2/bin/nvcc -DLLAMA_CURL=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
#   -DLLAMA_BUILD_HTML=OFF && cmake --build build --target llama-server llama-bench
set -euo pipefail

LLAMA_SERVER=${LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}
MODEL=${MODEL:-$(ls "${HF_HOME:-$HOME/hf_cache}"/hub/models--unsloth--Qwen3.5-9B-GGUF/snapshots/*/Qwen3.5-9B-Q8_0.gguf | head -1)}
MMPROJ=${MMPROJ-$(dirname "$MODEL")/mmproj-F16.gguf}
LOG_DIR="$(dirname "$0")/../data/logs"
mkdir -p "$LOG_DIR"

exec "$LLAMA_SERVER" -m "$MODEL" --alias qwen3.5-9b -ngl 99 -c 163840 --parallel 8 --jinja ${MMPROJ:+--mmproj "$MMPROJ"} \
  --host 127.0.0.1 --port "${PORT:-8080}" -fa auto --metrics 2>&1 | tee "$LOG_DIR/llama-server.log"
