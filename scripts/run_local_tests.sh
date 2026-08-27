#!/usr/bin/env bash
# 本地自动化测试入口（无需 Agent Server / Redis / 真实 LLM）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "请先运行: bash scripts/setup.sh" >&2
  exit 1
fi

PY=(.venv/bin/python -m pytest)

if [[ $# -eq 0 ]]; then
  set -- tests/ -q
fi

echo "== DeepTicket 本地测试 =="
"${PY[@]}" "$@"

echo ""
echo "全部通过。"
