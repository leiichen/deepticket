from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamChunk:
    """引擎 → 前端的 SSE 单帧（dataclass 默认值 ≈ 可选字段）。"""

    delta: str = ""
    conversation_id: str | None = None
    run_id: str | None = None
    done: bool = False
    activity: str | None = None  # 步骤区展示（思考/工具/系统）
    activity_kind: str | None = None
    confidence: dict[str, Any] | None = field(default=None)
    policy_denied: bool = False  # 软拒绝结束时为 True
    policy_message: str | None = None
