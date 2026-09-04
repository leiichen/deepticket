from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutboundPayload:
    source: str
    project_id: str
    external_id: str
    status: str
    reply: str = ""
    extensions: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class OutboundResult:
    method: str
    ok: bool
    detail: str = ""
    response_status: int | None = None
