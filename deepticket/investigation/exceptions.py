"""治理相关异常（从 OpenHandsEngine 抛出，由 ChatRunManager 捕获）。

注意：策略 DENY 的「软处理」通常不抛 ``PolicyDeniedError``——引擎会通知 Agent 继续解释，
Run 以 COMPLETED 结束；``error_message`` 里可带策略摘要。
以下异常主要用于 require_approval 硬暂停等场景。
"""
from __future__ import annotations


class PolicyDeniedError(RuntimeError):
    """MCP 工具被策略 deny 且需要硬停 Run（遗留路径，软 deny 已不常用）。"""


class PolicyApprovalRequiredError(RuntimeError):
    """MCP 工具需要审批：Run 应进入 waiting_approval，等人批准后再 resume。"""

    def __init__(
        self,
        message: str,
        *,
        approval_id: str,
        tool_name: str,
        mcp_server: str,
    ) -> None:
        super().__init__(message)
        self.approval_id = approval_id
        self.tool_name = tool_name
        self.mcp_server = mcp_server
