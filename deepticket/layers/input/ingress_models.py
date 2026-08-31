from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngressEvent:
    """外部系统推送的统一输入结构。"""

    source: str
    project_id: str
    external_id: str
    question: str
    image_urls: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)
