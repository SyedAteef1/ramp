#!/usr/bin/env bash
# ramp-cli — LOCAL test (no AWS, no cost). Author: Syed Ateef.
# Runs ramp against the sample logs in ../ramp-testbed/sample-logs using local mode.
set -euo pipefail
cd "$(dirname "$0")"

# 1) local logs instead of CloudWatch — no AWS needed
export RAMP_LOG_DIR="$HOME/personal-projects/ramp-testbed/sample-logs"

# 2) the model env (z.ai GLM) must already be exported by your ~/.zshrc:
#    ANTHROPIC_HOST=https://api.z.ai/api/anthropic  +  ANTHROPIC_API_KEY=<glm key>
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY not set — run:  source ~/.zshrc   (then re-run this script)"; exit 1
fi

# 3) deps for the MCP server (uses a venv so it's isolated)
if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip -q install -r mcp/requirements.txt
fi
# make goose's `python3` (for the stdio extension) resolve to the venv
export PATH="$PWD/.venv/bin:$PATH"

echo "== ramp: building the index (warm-up) =="
goose run --recipe recipes/index.yaml || true

echo "== ramp: diagnosing the 'upload' break (local logs) =="
goose run --recipe recipes/diagnose.yaml --params flow=upload --params minutes_back=999999
