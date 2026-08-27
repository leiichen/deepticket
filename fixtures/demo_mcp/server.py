"""Stdio MCP server for DeepTicket governance / timeline testing.

Run from repo root::

    .venv/bin/python -m fixtures.demo_mcp

Optional env:

- ``DEMO_EXTRA_TOOL=1`` — register ``demo_unknown_action`` for unknown-tool policy tests.

Tool names use underscores (``demo_lookup``) because OpenAI/LiteLLM requires ``^[a-zA-Z0-9_-]+$``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

_LOOKUP_DATA: dict[str, dict[str, Any]] = {
    "order-123": {
        "order_id": "order-123",
        "status": "paid",
        "amount_cents": 9900,
        "region": "cn-north",
    },
    "order-404": {
        "order_id": "order-404",
        "status": "not_found",
        "message": "no such order in demo fixture",
    },
}

_CONFIG_SNAPSHOT: dict[str, Any] = {
    "service": "checkout-api",
    "environment": "demo",
    "feature_flags": {"new_payment_flow": True, "strict_validation": False},
    "timeouts_ms": {"upstream": 3000, "db": 1500},
}

mcp = FastMCP("deepticket-demo")


@mcp.tool(name="demo_lookup")
def demo_lookup(key: str) -> str:
    """Look up a fixed demo record by key (e.g. order-123). Deterministic per key."""
    record = _LOOKUP_DATA.get(key.strip())
    if record is None:
        payload = {
            "found": False,
            "key": key,
            "available_keys": sorted(_LOOKUP_DATA.keys()),
        }
    else:
        payload = {"found": True, "record": record}
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool(name="demo_read_config")
def demo_read_config(section: str = "all") -> str:
    """Return a fixed in-memory config snapshot; section filters top-level keys when not 'all'."""
    section = section.strip().lower()
    if section in {"", "all", "*"}:
        payload = {"section": "all", "config": _CONFIG_SNAPSHOT}
    elif section in _CONFIG_SNAPSHOT:
        payload = {"section": section, "value": _CONFIG_SNAPSHOT[section]}
    else:
        payload = {
            "section": section,
            "error": "unknown section",
            "available_sections": sorted(_CONFIG_SNAPSHOT.keys()),
        }
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool(name="demo_echo")
def demo_echo(message: str, tag: str = "") -> str:
    """Echo inputs back as JSON — useful for distinguishing multiple tool calls in a timeline."""
    return json.dumps(
        {"message": message, "tag": tag, "length": len(message)},
        ensure_ascii=False,
    )


@mcp.tool(name="demo_delete_resource")
def demo_delete_resource(resource_id: str, resource_type: str = "generic") -> str:
    """Simulate a destructive action; never deletes anything (dry_run only)."""
    return json.dumps(
        {
            "dry_run": True,
            "action": "delete",
            "resource_id": resource_id,
            "resource_type": resource_type,
            "deleted": False,
        },
        ensure_ascii=False,
    )


@mcp.tool(name="demo_exec_command")
def demo_exec_command(command: str, cwd: str = "/tmp") -> str:
    """Simulate shell execution; does not run the command."""
    return json.dumps(
        {
            "dry_run": True,
            "would_run": command,
            "cwd": cwd,
            "executed": False,
        },
        ensure_ascii=False,
    )


if os.environ.get("DEMO_EXTRA_TOOL", "").strip() in {"1", "true", "yes"}:

    @mcp.tool(name="demo_unknown_action")
    def demo_unknown_action(target: str = "resource") -> str:
        """Optional tool for unknown_tool_mode tests (enable via DEMO_EXTRA_TOOL=1)."""
        return json.dumps({"action": "unknown", "target": target}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
