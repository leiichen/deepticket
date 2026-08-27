"""OpenHands 事件 → Investigation RunEvent 映射。

OpenHands WebSocket 推送 JSON 事件（``kind``: MessageEvent / ActionEvent / …），
本模块负责：
1. ``extract_mcp_tool_call`` — 从 ActionEvent 解析 MCP 工具名（治理 Hook 用）
2. ``map_openhands_event`` — 转成 ``RunEventType`` + payload（审计时间线用）

``isinstance(x, dict)`` 是 Python 动态类型下的常见防御写法（OH 事件 schema 不固定）。
"""
from __future__ import annotations

import json
from typing import Any

from deepticket.investigation.events import RunEventType
from deepticket.layers.output.activity import format_agent_activity


def _preview(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _message_text(event: dict[str, Any]) -> str:
    content = event.get("content") or event.get("message")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]
        return " ".join(parts).strip()
    llm = event.get("llm_message") or {}
    llm_content = llm.get("content")
    if isinstance(llm_content, list):
        parts = [
            block.get("text", "")
            for block in llm_content
            if isinstance(block, dict) and block.get("text")
        ]
        return " ".join(parts).strip()
    if isinstance(llm_content, str):
        return llm_content.strip()
    return ""


def extract_mcp_tool_call(event: dict[str, Any]) -> tuple[str, str, dict[str, Any]] | None:
    """从 ActionEvent 提取 (mcp_server, tool_name, arguments)。"""
    if event.get("kind") != "ActionEvent":
        return None
    action = event.get("action") or {}
    if not isinstance(action, dict):
        return None

    mcp_server = str(action.get("mcp_server") or action.get("server") or "").strip()
    tool_name = str(
        action.get("tool_name") or action.get("name") or event.get("tool_name") or ""
    ).strip()
    arguments = action.get("arguments") or action.get("args") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    if not tool_name and isinstance(action.get("tool"), str):
        tool_name = action["tool"].strip()

    if tool_name.startswith("demo_"):
        return mcp_server or "deepticket-demo", tool_name, arguments

    if mcp_server or action.get("type") == "mcp" or event.get("tool_name") == "mcp":
        return mcp_server or "unknown", tool_name or "unknown", arguments

    return None


def map_openhands_event(event: dict[str, Any]) -> tuple[RunEventType, dict[str, Any]] | None:
    kind = event.get("kind") or ""

    if kind == "MessageEvent" and event.get("source") == "agent":
        text = _message_text(event)
        if not text:
            return None
        return RunEventType.AGENT_MESSAGE, {
            "role": "assistant",
            "text_preview": _preview(text),
        }

    if kind == "ActionEvent":
        mcp = extract_mcp_tool_call(event)
        tool = str(event.get("tool_name") or "").strip()
        action = event.get("action") or {}
        if mcp:
            mcp_server, tool_name, arguments = mcp
            return RunEventType.TOOL_CALL, {
                "mcp_server": mcp_server,
                "tool": tool_name,
                "arguments_preview": _preview(arguments),
            }
        return RunEventType.TOOL_CALL, {
            "tool": tool or "unknown",
            "arguments_preview": _preview(action),
            "summary": _preview(event.get("summary") or ""),
        }

    if kind == "ObservationEvent":
        observation = event.get("observation") or {}
        body = ""
        if isinstance(observation, dict):
            for key in ("content", "message", "output", "text"):
                val = observation.get(key)
                if isinstance(val, str) and val.strip():
                    body = val.strip()
                    break
        tool = str(event.get("tool_name") or "tool").strip()
        status = "error" if isinstance(observation, dict) and observation.get("is_error") else "ok"
        activity = format_agent_activity(event)
        summary_text = body or (activity.text if activity else "")
        return RunEventType.TOOL_RESULT, {
            "tool": tool,
            "status": status,
            "summary": _preview(summary_text),
        }

    if kind in {"ConversationErrorEvent", "AgentErrorEvent"}:
        return RunEventType.ERROR, {
            "code": str(event.get("code") or kind),
            "message": _preview(event.get("detail") or event.get("message") or event.get("error")),
        }

    return None
