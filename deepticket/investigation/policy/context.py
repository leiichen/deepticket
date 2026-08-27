"""工具治理上下文（策略链输入 DTO）。

类比 Java：类似 ``SecurityContext`` + 方法参数，供可插拔 ``ToolGovernanceStrategy`` 使用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolInvocationContext:
    """单次 MCP 工具调用的完整上下文。"""

    project_id: str
    mcp_server: str
    tool_name: str
    arguments: dict[str, Any]
    tool_known: bool = True
    run_id: str = ""
    uid: str = ""
    chat_id: str | None = None
    oh_conversation_id: str | None = None
    user_is_admin: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def with_updates(self, **kwargs: Any) -> ToolInvocationContext:
        data = {
            "project_id": self.project_id,
            "mcp_server": self.mcp_server,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "tool_known": self.tool_known,
            "run_id": self.run_id,
            "uid": self.uid,
            "chat_id": self.chat_id,
            "oh_conversation_id": self.oh_conversation_id,
            "user_is_admin": self.user_is_admin,
            "extra": dict(self.extra),
        }
        data.update(kwargs)
        return ToolInvocationContext(**data)
