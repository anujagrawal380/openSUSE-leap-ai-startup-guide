#!/usr/bin/env bash
# Smoke test a prepared suse-assist demo/runtime.
#
# Defaults assume the command is run from a source checkout. Override with:
#   SUSE_ASSIST_CMD="suse-assist" CONFIG=/path/config.yaml MODEL_TIER=test ./scripts/demo_smoke_test.sh

set -euo pipefail

CONFIG="${CONFIG:-config.yaml}"
MODEL_TIER="${MODEL_TIER:-test}"
PROMPT="${PROMPT:-How do I install Firefox using zypper?}"
RAG_QUERY="${RAG_QUERY:-zypper install package}"
WEB_URL="${WEB_URL:-http://127.0.0.1:7860/}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
SUSE_ASSIST_CMD="${SUSE_ASSIST_CMD:-python3 -m opensuse_ai.cli}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SKIP_CLI="${SKIP_CLI:-0}"
SKIP_RAG="${SKIP_RAG:-0}"
SKIP_WEB="${SKIP_WEB:-0}"

read -r -a SUSE_ASSIST_ARGS <<< "$SUSE_ASSIST_CMD"

log() {
    printf '[smoke] %s\n' "$*"
}

run_cli_demo() {
    log "CLI demo answer"
    {
        printf '%s\n' "$PROMPT"
        printf 'quit\n'
    } | timeout "$TIMEOUT_SECONDS" "${SUSE_ASSIST_ARGS[@]}" \
        --config "$CONFIG" chat --demo --model-tier "$MODEL_TIER" \
        >/tmp/suse-assist-cli-smoke.out

    if ! grep -Eiq 'zypper|openSUSE|package|YaST' /tmp/suse-assist-cli-smoke.out; then
        cat /tmp/suse-assist-cli-smoke.out
        printf 'CLI smoke output did not contain expected openSUSE terms\n' >&2
        return 1
    fi
}

run_rag_retrieval() {
    log "RAG retrieval"
    "$PYTHON_BIN" - "$CONFIG" "$RAG_QUERY" <<'PY'
import sys

from opensuse_ai.config import Config
from opensuse_ai.rag import RAGPipeline

cfg = Config.from_yaml(sys.argv[1])
rag = RAGPipeline(cfg)
if not rag.is_populated:
    raise SystemExit(f"vector store is not populated: {cfg.rag.persist_directory}")
results = rag.retrieve(sys.argv[2])
if not results:
    raise SystemExit("RAG retrieval returned no results")
print(f"retrieved {len(results)} chunks; top={results[0]['metadata'].get('title', '')}")
PY
}

run_web_endpoint() {
    log "web endpoint"
    python3 - "$WEB_URL" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=10) as resp:
    body = resp.read(4096).decode("utf-8", errors="replace")
    if resp.status >= 400:
        raise SystemExit(f"{url} returned HTTP {resp.status}")
    if "openSUSE" not in body and "gradio" not in body.lower():
        raise SystemExit(f"{url} did not look like the assistant web UI")
print(f"{url} ok")
PY
}

if [[ "$SKIP_CLI" != "1" ]]; then
    run_cli_demo
fi
if [[ "$SKIP_RAG" != "1" ]]; then
    run_rag_retrieval
fi
if [[ "$SKIP_WEB" != "1" ]]; then
    run_web_endpoint
fi

log "all requested smoke checks passed"
