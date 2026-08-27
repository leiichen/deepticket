"""MCP 工具治理网关（策略评估 + 审计事件 + 审批单创建）。

拦截层级：
1. **PreToolUse hook**（``pre_tool_use.py``）— OH execute 前硬拦截，DENY → 工具零调用
2. **WebSocket gate**（``OpenHandsEngine._push_event``）— 审计与兜底

``ToolGovernanceStrategy`` 子类可通过 ``PolicyEngine(extra_strategies=[...])`` 注入。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.approvals import ApprovalRequestStore
from deepticket.investigation.events import RunEventStore, RunEventType
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.engine import PolicyEngine
from deepticket.investigation.policy.evaluation import PolicyEvaluation
from deepticket.investigation.registry.mcp_tools import McpToolRegistry


@dataclass(frozen=True)
class ToolGovernanceResult:
    evaluation: PolicyEvaluation
    blocked: bool = False
    waiting_approval: bool = False
    hard_block: bool = False
    block_message: str | None = None
    approval_id: str | None = None


class ToolGovernanceGate:
    """MCP 工具治理入口。"""

    def __init__(
        self,
        policy_engine: PolicyEngine,
        event_store: RunEventStore | None = None,
        *,
        approval_store: ApprovalRequestStore | None = None,
        tool_registry: McpToolRegistry | None = None,
    ) -> None:
        self._policy = policy_engine
        self._events = event_store
        self._approvals = approval_store
        self._registry = tool_registry

    def evaluate_context(self, ctx: ToolInvocationContext) -> ToolGovernanceResult:
        tool_known = self._is_known_tool(ctx.project_id, ctx.mcp_server, ctx.tool_name)
        ctx = ctx.with_updates(tool_known=tool_known)

        if (
            ctx.run_id
            and self._approvals is not None
            and self._approvals.consume_tool_grant(
                ctx.project_id, ctx.run_id, ctx.tool_name
            )
        ):
            evaluation = PolicyEvaluation(
                decision=PolicyDecision.ALLOW,
                reason="one-time grant after operator approval",
                matched_rule="approval.grant",
            )
            if self._events is not None:
                self._events.append(
                    ctx.project_id,
                    ctx.run_id,
                    RunEventType.POLICY_DECISION,
                    {
                        "tool": ctx.tool_name,
                        "mcp_server": ctx.mcp_server,
                        "decision": evaluation.decision.value,
                        "reason": evaluation.reason,
                        "matched_rule": evaluation.matched_rule,
                        "uid": ctx.uid,
                    },
                )
            return ToolGovernanceResult(evaluation=evaluation, blocked=False)

        evaluation = self._policy.evaluate(ctx)

        if ctx.run_id and self._events is not None:
            self._events.append(
                ctx.project_id,
                ctx.run_id,
                RunEventType.POLICY_DECISION,
                {
                    "tool": ctx.tool_name,
                    "mcp_server": ctx.mcp_server,
                    "decision": evaluation.decision.value,
                    "reason": evaluation.reason,
                    "matched_rule": evaluation.matched_rule,
                    "uid": ctx.uid,
                },
            )

        if evaluation.decision is PolicyDecision.ALLOW:
            return ToolGovernanceResult(evaluation=evaluation, blocked=False)

        if evaluation.decision is PolicyDecision.DENY:
            message = (
                f"Tool {ctx.tool_name} denied by policy ({evaluation.matched_rule})"
            )
            if ctx.run_id:
                self._record_block_event(
                    ctx.project_id, ctx.run_id, message, code="policy_denied"
                )
            return ToolGovernanceResult(
                evaluation=evaluation,
                blocked=True,
                hard_block=True,
                block_message=message,
            )

        message = (
            f"Tool {ctx.tool_name} requires approval ({evaluation.matched_rule}); "
            "waiting for operator decision"
        )
        approval_id = None
        if self._approvals is not None and ctx.run_id:
            pending = self._approvals.get_pending_for_run(ctx.project_id, ctx.run_id)
            if pending is not None and pending.tool_name == ctx.tool_name:
                approval_id = pending.approval_id
            else:
                request = self._approvals.create(
                    project_id=ctx.project_id,
                    run_id=ctx.run_id,
                    tool_name=ctx.tool_name,
                    mcp_server=ctx.mcp_server,
                    arguments=ctx.arguments,
                )
                approval_id = request.approval_id
        if ctx.run_id:
            self._record_block_event(
                ctx.project_id, ctx.run_id, message, code="approval_required"
            )
        return ToolGovernanceResult(
            evaluation=evaluation,
            blocked=True,
            waiting_approval=True,
            hard_block=True,
            block_message=message,
            approval_id=approval_id,
        )

    def evaluate_mcp_tool(
        self,
        *,
        project_id: str,
        run_id: str,
        mcp_server: str,
        tool_name: str,
        arguments: dict[str, Any],
        uid: str = "",
        chat_id: str | None = None,
        oh_conversation_id: str | None = None,
        user_is_admin: bool = False,
    ) -> ToolGovernanceResult:
        ctx = ToolInvocationContext(
            project_id=project_id,
            run_id=run_id,
            uid=uid,
            chat_id=chat_id,
            oh_conversation_id=oh_conversation_id,
            user_is_admin=user_is_admin,
            mcp_server=mcp_server,
            tool_name=tool_name,
            arguments=arguments,
        )
        return self.evaluate_context(ctx)

    def _is_known_tool(self, project_id: str, mcp_server: str, tool_name: str) -> bool:
        if self._registry is None or not mcp_server.strip():
            return True
        tools = self._registry.get_tools(project_id, mcp_server)
        if not tools:
            return True
        names = {item.name for item in tools}
        return tool_name in names

    def _record_block_event(
        self,
        project_id: str,
        run_id: str,
        message: str,
        *,
        code: str,
    ) -> None:
        if self._events is None:
            return
        self._events.append(
            project_id,
            run_id,
            RunEventType.ERROR,
            {"code": code, "message": message},
        )
