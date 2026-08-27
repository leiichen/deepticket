#!/usr/bin/env bash
# 本地自动化测试：Investigation Run + 工具治理（无需 Agent Server / Redis）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "请先运行: bash scripts/setup.sh" >&2
  exit 1
fi

PY=(.venv/bin/python -m pytest)

echo "== Investigation & Governance 套件 =="
"${PY[@]}" \
  tests/test_investigation_run.py \
  tests/test_investigation_p0.py \
  tests/test_governance_strategy.py \
  tests/test_governance_gate.py \
  tests/test_governance_integration.py \
  tests/test_runs_api.py \
  tests/test_chat_runs.py \
  tests/test_demo_mcp.py \
  -q "$@"

echo ""
echo "全部通过。"
