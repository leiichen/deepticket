from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepticket.layers.output.confidence import compute_confidence
from deepticket.layers.output.models import StreamChunk


@dataclass
class IngressJobResult:
    job_id: str
    status: str
    source: str
    project_id: str
    external_id: str
    reply: str
    extensions: dict[str, Any]
    error: str | None = None
    outbound_method: str = ""
    outbound_ok: bool = False
    outbound_detail: str = ""


async def collect_stream_text(
    chunks,
) -> tuple[str, str | None, dict[str, Any] | None]:
    parts: list[str] = []
    activities: list[dict[str, str]] = []
    conversation_id: str | None = None
    confidence: dict[str, Any] | None = None
    async for chunk in chunks:
        if isinstance(chunk, StreamChunk):
            if chunk.conversation_id:
                conversation_id = chunk.conversation_id
            if chunk.activity:
                activities.append(
                    {
                        "text": chunk.activity,
                        "kind": chunk.activity_kind or "default",
                    }
                )
            if chunk.delta:
                parts.append(chunk.delta)
            if chunk.confidence:
                confidence = chunk.confidence
    reply = "".join(parts)
    if confidence is None and reply:
        confidence = compute_confidence(
            activities=activities,
            reply=reply,
            ok=True,
        )
    return reply, conversation_id, confidence
