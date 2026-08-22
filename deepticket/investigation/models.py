from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunSource(StrEnum):
    CHAT = "chat"
    INGRESS = "ingress"
    TICKET = "ticket"


TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)


@dataclass
class InvestigationRun:
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
