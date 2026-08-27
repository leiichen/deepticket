#!/usr/bin/env bash
# OpenHands PreToolUse：必须用项目 venv，否则 import 失败 → exit 1 → 工具仍会被调用
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m deepticket.investigation.governance.pre_tool_use
