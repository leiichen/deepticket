"""OpenHands PreToolUse 命令 Hook（stdin JSON → 策略评估 → exit 2 硬拦截）。

由 ``hook.build_hook_config()`` 注册到 conversation；OH 在 MCP execute **之前**同步调用。
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from deepticket.config.loader import load_app_config
from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.approvals import ApprovalRequestStore
from deepticket.investigation.events import RunEventStore
from deepticket.investigation.governance.gate import ToolGovernanceGate
from deepticket.investigation.governance.approval_pause import mark_run_waiting_approval
from deepticket.investigation.governance.session_context import GovernanceContextStore
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.engine import PolicyEngine
from deepticket.investigation.registry.mcp_tools import McpToolRegistry
from deepticket.investigation.store import InvestigationRunStore
from deepticket.layers.storage import create_storage
from deepticket.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


def _parse_tool_arguments(tool_input: dict[str, Any] | None) -> dict[str, Any]:
    if not tool_input:
        return {}
    data = tool_input.get("data")
    if isinstance(data, dict):
        return dict(data)
    if isinstance(tool_input, dict):
        return dict(tool_input)
    return {}


def _infer_mcp_server(tool_name: str, metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("mcp_server") or metadata.get("mcpServer") or "").strip()
    if explicit:
        return explicit
    if tool_name.startswith("demo_"):
        return "deepticket-demo"
    return "unknown"


def _build_stack() -> tuple[
    ToolGovernanceGate,
    GovernanceContextStore,
    RunEventStore,
    Any,
]:
    config = load_app_config(dotenv_root=PROJECT_ROOT)
    storage = create_storage(config.storage)
    run_store = InvestigationRunStore(storage)
    event_store = RunEventStore(storage, run_store=run_store)
    approval_store = ApprovalRequestStore(storage)
    registry = McpToolRegistry(storage)
    policy = PolicyEngine(config.tool_governance)
    gate = ToolGovernanceGate(
        policy,
        event_store,
        approval_store=approval_store,
        tool_registry=registry,
    )
    return gate, GovernanceContextStore(storage), event_store, storage


def evaluate_hook_event(event: dict[str, Any]) -> tuple[bool, str]:
    """返回 (allow, message)。allow=False 时 message 写入 stderr 并 exit 2。"""
    tool_name = str(event.get("tool_name") or "").strip()
    if not tool_name:
        return True, ""

    session_id = str(
        event.get("session_id")
        or event.get("metadata", {}).get("session_id")
        or ""
    ).strip()
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    arguments = _parse_tool_arguments(event.get("tool_input"))
    mcp_server = _infer_mcp_server(tool_name, metadata)

    gate, sessions, event_store, storage = _build_stack()
    session = sessions.get_by_conversation(session_id) if session_id else None

    project_id = session.project_id if session else str(metadata.get("project_id") or "default")
    run_id = session.run_id if session else str(metadata.get("run_id") or "")
    uid = session.uid if session else str(metadata.get("uid") or "unknown")
    chat_id = session.chat_id if session else metadata.get("chat_id")
    user_is_admin = session.user_is_admin if session else bool(metadata.get("user_is_admin"))

    if not run_id:
        ctx = ToolInvocationContext(
            project_id=project_id,
            mcp_server=mcp_server,
            tool_name=tool_name,
            arguments=arguments,
            uid=uid,
            chat_id=chat_id,
            oh_conversation_id=session_id or None,
            user_is_admin=user_is_admin,
        )
        evaluation = gate._policy.evaluate(ctx)  # noqa: SLF001
        if evaluation.decision is PolicyDecision.ALLOW:
            return True, ""
        return False, f"Tool {tool_name} blocked by policy ({evaluation.matched_rule})"

    result = gate.evaluate_mcp_tool(
        project_id=project_id,
        run_id=run_id,
        mcp_server=mcp_server,
        tool_name=tool_name,
        arguments=arguments,
        uid=uid,
        chat_id=chat_id,
        oh_conversation_id=session_id or None,
        user_is_admin=user_is_admin,
    )
    if not result.blocked:
        return True, ""
    message = str(result.block_message or "Tool blocked by policy")
    if result.waiting_approval:
        mark_run_waiting_approval(
            storage,
            project_id=project_id,
            run_id=run_id,
            uid=uid,
            chat_id=str(chat_id) if chat_id else None,
            message=message,
            event_store=event_store,
        )
    return False, message


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(f"invalid hook stdin JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    allow, message = evaluate_hook_event(event)
    if allow:
        sys.exit(0)
    print(message, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
