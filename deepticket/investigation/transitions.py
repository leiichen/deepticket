"""InvestigationRun 状态机：允许的 (from, to) 转换表。

设计原则（类似 Java 里手写 State 枚举 + 校验）：
- 所有状态变更必须走 ``InvestigationRunStore.transition()``
- ``validate_transition()`` 在此白名单表上校验，非法转换抛 ``RunTransitionError``
- 终态（completed/failed/blocked/cancelled）不可再转出

常见路径：
  chat:     CREATED → RUNNING → COMPLETED
  deny:     RUNNING → COMPLETED（软拒绝：Agent 仍会解释；见 engine）
  approval: RUNNING → WAITING_APPROVAL → RUNNING（批准后 resume）
  ingress:  CREATED → QUEUED → RUNNING → COMPLETED
"""
from __future__ import annotations

from deepticket.investigation.models import TERMINAL_RUN_STATUSES, RunStatus


class RunTransitionError(ValueError):
    """非法 Run 状态转换（类似 IllegalStateException）。"""


ALLOWED_RUN_TRANSITIONS: frozenset[tuple[RunStatus, RunStatus]] = frozenset(
    {
        (RunStatus.CREATED, RunStatus.QUEUED),
        (RunStatus.CREATED, RunStatus.RUNNING),
        (RunStatus.CREATED, RunStatus.CANCELLED),
        (RunStatus.QUEUED, RunStatus.RUNNING),
        (RunStatus.QUEUED, RunStatus.CANCELLED),
        (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL),
        (RunStatus.RUNNING, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunStatus.FAILED),
        (RunStatus.RUNNING, RunStatus.BLOCKED),
        (RunStatus.RUNNING, RunStatus.CANCELLED),
        (RunStatus.WAITING_APPROVAL, RunStatus.RUNNING),
        (RunStatus.WAITING_APPROVAL, RunStatus.FAILED),
        (RunStatus.WAITING_APPROVAL, RunStatus.BLOCKED),
        (RunStatus.WAITING_APPROVAL, RunStatus.CANCELLED),
    }
)


def validate_transition(from_status: RunStatus, to_status: RunStatus) -> None:
    if from_status in TERMINAL_RUN_STATUSES:
        raise RunTransitionError(
            f"run already terminal ({from_status.value}); cannot transition to {to_status.value}"
        )
    if (from_status, to_status) not in ALLOWED_RUN_TRANSITIONS:
        raise RunTransitionError(
            f"transition not allowed: {from_status.value} -> {to_status.value}"
        )
