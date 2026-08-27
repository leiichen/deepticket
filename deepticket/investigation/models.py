"""InvestigationRun 领域模型。

类比 Java：
- ``StrEnum`` ≈ ``enum X implements String``（序列化时用 ``.value`` 字符串）
- ``@dataclass`` ≈ Lombok ``@Data`` / record（自动生成 ``__init__``、字段，无样板代码）
- ``str | None`` ≈ ``Optional<String>``（Python 3.10+ 联合类型写法）
- ``frozenset`` ≈ ``Collections.unmodifiableSet``（不可变集合，适合常量表）

InvestigationRun 表示「一次 Agent 调查任务」，与 OpenHands 的 conversation 不同：
一个 chat 可有多条 Run（用户每发一条消息通常新建一个 Run）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    """Run 生命周期状态（显式状态机，见 ``transitions.py``）。"""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"  # require_approval 策略命中，等人点批准
    COMPLETED = "completed"
    FAILED = "failed"  # 系统/Runtime 异常
    BLOCKED = "blocked"  # 策略拒绝或审批被拒（终态，但不一定代表系统故障）
    CANCELLED = "cancelled"


class RunSource(StrEnum):
    """Run 来源：聊天 / Ingress 队列 / 工单 API。"""

    CHAT = "chat"
    INGRESS = "ingress"
    TICKET = "ticket"


# 终态：进入后不可再 transition（类似 Java 状态机里的 terminal state）
TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.BLOCKED, RunStatus.CANCELLED}
)


@dataclass
class InvestigationRun:
    """一次 Agent 执行的持久化实体（存 Redis/Local JSON）。"""

    run_id: str
    project_id: str
    uid: str
    source: RunSource
    status: RunStatus
    created_at: str
    updated_at: str
    chat_id: str | None = None
    ingress_job_id: str | None = None
    ticket_id: str | None = None
    oh_conversation_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    tool_call_count: int = 0
    event_count: int = 0

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "uid": self.uid,
            "source": self.source.value,
            "status": self.status.value,
            "chat_id": self.chat_id,
            "ingress_job_id": self.ingress_job_id,
            "ticket_id": self.ticket_id,
            "oh_conversation_id": self.oh_conversation_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_message": self.error_message,
            "tool_call_count": self.tool_call_count,
            "event_count": self.event_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InvestigationRun:
        return cls(
            run_id=str(data["run_id"]),
            project_id=str(data["project_id"]),
            uid=str(data["uid"]),
            source=RunSource(str(data["source"])),
            status=RunStatus(str(data["status"])),
            chat_id=data.get("chat_id") or None,
            ingress_job_id=data.get("ingress_job_id") or None,
            ticket_id=data.get("ticket_id") or None,
            oh_conversation_id=data.get("oh_conversation_id") or None,
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            started_at=data.get("started_at") or None,
            finished_at=data.get("finished_at") or None,
            error_message=data.get("error_message") or None,
            tool_call_count=int(data.get("tool_call_count") or 0),
            event_count=int(data.get("event_count") or 0),
        )


@dataclass
class RunStatusChange:
    run_id: str
    from_status: RunStatus
    to_status: RunStatus
    timestamp: str
    reason: str | None = field(default=None)
