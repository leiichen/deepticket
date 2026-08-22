from __future__ import annotations

from deepticket.investigation.models import TERMINAL_RUN_STATUSES, RunStatus


class RunTransitionError(ValueError):
    """非法 Run 状态转换。"""


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
        (RunStatus.RUNNING, RunStatus.CANCELLED),
        (RunStatus.WAITING_APPROVAL, RunStatus.RUNNING),
        (RunStatus.WAITING_APPROVAL, RunStatus.FAILED),
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
