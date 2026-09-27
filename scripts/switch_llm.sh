#!/usr/bin/env bash
# Stop the running llama-server and start another model (benchmark runs, one model at a time).
#   scripts/switch_llm.sh <alias> <model.gguf> <mmproj.gguf> [ctx]
set -euo pipefail
cd "$(dirname "$0")/.."
for pid in $(pgrep -x llama-server || true); do kill "$pid"; done
for _ in $(seq 1 30); do pgrep -x llama-server >/dev/null || break; sleep 1; done
ALIAS="$1" MODEL="$2" MMPROJ="$3" CTX="${4:-98304}" nohup scripts/serve_llm.sh >/dev/null 2>&1 &
for _ in $(seq 1 120); do
  curl -sf localhost:8080/health >/dev/null && { echo "ready: $1"; exit 0; }
  sleep 5
done
echo "server did not start: see data/logs/llama-server.log" >&2
exit 1
