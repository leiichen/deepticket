"""Run 内 append-only 事件流（审计时间线）。

每条 Run 有单调递增的 ``seq``（Redis INCR 原子计数，类似 Redis INCR 或 DB sequence）。
事件类型供 Web「运行详情」和 ``GET /api/runs/{id}/events`` 使用。

与 SSE「步骤/思考过程」区别：
- SSE activity：面向用户的可读摘要（``format_agent_activity``）
- RunEvent：结构化审计记录，可 REST 查询、可回放
"""
from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from deepticket.layers.storage.base import StorageBackend
from deepticket.utils.time import utc_now_iso

_NS_RUN_EVENT = "inv_run_event"
_NS_RUN_EVENTS = "inv_run_events"
_NS_RUN_SEQ = "inv_run_seq"


class RunEventType(StrEnum):
    RUN_CREATED = "run_created"
    RUN_STATUS_CHANGED = "run_status_changed"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    POLICY_DECISION = "policy_decision"
    ERROR = "error"
    RUN_COMPLETED = "run_completed"


class RunEventStore:
    """Run 内 append-only 事件序列（Redis INCR 保证 seq 单调）。"""

    def __init__(self, storage: StorageBackend, *, run_store: object | None = None) -> None:
        self.storage = storage
        # 可选回写 Run 统计；用 object + getattr 避免与 store 循环 import
        self._run_store = run_store

    def append(
        self,
        project_id: str,
        run_id: str,
        event_type: RunEventType,
        payload: dict[str, Any],
        *,
        oh_event_id: str | None = None,
    ) -> dict[str, Any]:
        seq = self._next_seq(project_id, run_id)
        event_id = uuid.uuid4().hex
        doc = {
            "event_id": event_id,
            "run_id": run_id,
            "project_id": project_id,
            "seq": seq,
            "type": event_type.value,
            "timestamp": utc_now_iso(),
            "payload": payload,
            "oh_event_id": oh_event_id,
        }
        self.storage.set_json(_NS_RUN_EVENT, self._event_key(project_id, event_id), doc)
        self.storage.zadd(
            _NS_RUN_EVENTS,
            self._run_index_key(project_id, run_id),
            {event_id: float(seq)},
        )
        if self._run_store is not None:
            bump = getattr(self._run_store, "bump_event_stats", None)
            if callable(bump):
                bump(project_id, run_id, event_type)
        return doc

    def list_events(
        self,
        project_id: str,
        run_id: str,
        *,
        after_seq: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        event_ids = self.storage.zrange(
            _NS_RUN_EVENTS, self._run_index_key(project_id, run_id), 0, -1
        )
        events: list[dict[str, Any]] = []
        for event_id in event_ids:
            doc = self.storage.get_json(_NS_RUN_EVENT, self._event_key(project_id, event_id))
            if not doc:
                continue
            seq = int(doc.get("seq") or 0)
            if seq <= after_seq:
                continue
            events.append(doc)
        events.sort(key=lambda item: int(item.get("seq") or 0))
        return events[: max(1, min(limit, 500))]

    def _next_seq(self, project_id: str, run_id: str) -> int:
        # Redis: INCR 原子；Local: 文件模拟（单进程测试够用）
        key = self._seq_key(project_id, run_id)
        return self.storage.incr(_NS_RUN_SEQ, key)

    @staticmethod
    def _event_key(project_id: str, event_id: str) -> str:
        return f"{project_id}:{event_id}"

    @staticmethod
    def _run_index_key(project_id: str, run_id: str) -> str:
        return f"{project_id}:{run_id}"

    @staticmethod
    def _seq_key(project_id: str, run_id: str) -> str:
        return f"{project_id}:{run_id}"
