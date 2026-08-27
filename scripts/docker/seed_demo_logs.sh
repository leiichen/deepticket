#!/usr/bin/env bash
# 为 ad_agent Demo 预生成 campaign_metrics.log（容器内或本机均可运行）。
# 前提：已配置 ad-agent 仓库并完成「同步知识库」。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

candidates=(
  "${ROOT}/workspace/default/project/ad-agent"
  "${ROOT}/workspace/project/ad-agent"
)

for AGENT_DIR in "${candidates[@]}"; do
  [[ -d "${AGENT_DIR}" ]] || continue
  GEN="${AGENT_DIR}/scripts/generate_campaign_data.py"
  METRICS="${AGENT_DIR}/data/campaign_metrics.log"
  if [[ ! -f "${GEN}" ]]; then
    continue
  fi
  if [[ -s "${METRICS}" ]]; then
    echo "OK: 已有 demo log → ${METRICS}"
    exit 0
  fi
  echo "生成 demo log: ${AGENT_DIR}"
  (
    cd "${AGENT_DIR}"
    python3 scripts/generate_campaign_data.py --start 2026-07-24 --end 2026-08-01
  )
  echo "OK: ${METRICS}"
  exit 0
done

echo "未找到 ad-agent workspace；请先配置 knowledge.repos 并同步知识库。" >&2
exit 1
