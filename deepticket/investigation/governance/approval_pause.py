"""require_approval 命中时：Run 进入 waiting_approval，并同步聊天状态（供前端展示审批）。"""
from __future__ import annotations

import logging

from deepticket.investigation.events import RunEventStore
from deepticket.investigation.models import RunStatus
from deepticket.investigation.store import InvestigationRunStore
from deepticket.investigation.transitions import RunTransitionError
from deepticket.layers.storage.base import StorageBackend
from deepticket.layers.storage.chat_history import ChatHistoryStore

logger = logging.getLogger(__name__)


def mark_run_waiting_approval(
    storage: StorageBackend,
    *,
    project_id: str,
    run_id: str,
    uid: str,
    chat_id: str | None,
    message: str,
    event_store: RunEventStore | None = None,
) -> None:
    """PreToolUse / WS gate 命中 require_approval 时调用；幂等。"""
    runs = InvestigationRunStore(storage)
    run = runs.get_run(project_id, run_id)
    if run is None:
        return

    if run.status is not RunStatus.WAITING_APPROVAL:
        try:
            runs.transition(
                project_id,
                run_id,
                RunStatus.WAITING_APPROVAL,
                error_message=message[:500],
                event_store=event_store,
            )
        except RunTransitionError as exc:
            logger.warning("mark_run_waiting_approval skipped: %s", exc)

    if chat_id and uid:
        try:
            ChatHistoryStore(storage).set_agent_run_status(
                project_id,
                uid,
                chat_id,
                status="waiting_approval",
                error=message[:500],
            )
        except KeyError:
            logger.debug("chat not found for waiting_approval: %s", chat_id)
