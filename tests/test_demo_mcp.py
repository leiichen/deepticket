from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]

BASE_TOOL_NAMES = {
    "demo.lookup",
    "demo.read_config",
    "demo.echo",
    "demo.delete_resource",
    "demo.exec_command",
}


def _server_params(*, extra_tool: bool = False) -> StdioServerParameters:
    env = None
    if extra_tool:
        env = {"DEMO_EXTRA_TOOL": "1"}
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "fixtures.demo_mcp"],
        cwd=str(REPO_ROOT),
        env=env,
    )


@asynccontextmanager
async def _demo_session(*, extra_tool: bool = False) -> AsyncIterator[ClientSession]:
    params = _server_params(extra_tool=extra_tool)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.asyncio
async def test_list_tools_includes_demo_fixture_tools():
    async with _demo_session() as session:
        result = await session.list_tools()
        names = {tool.name for tool in result.tools}
        assert BASE_TOOL_NAMES <= names
        assert "demo.unknown_action" not in names


@pytest.mark.asyncio
async def test_lookup_returns_stable_record():
    async with _demo_session() as session:
        first = await session.call_tool("demo.lookup", {"key": "order-123"})
        second = await session.call_tool("demo.lookup", {"key": "order-123"})
        assert first.content
        assert second.content
        payload_first = json.loads(first.content[0].text)
        payload_second = json.loads(second.content[0].text)
        assert payload_first == payload_second
        assert payload_first["found"] is True
        assert payload_first["record"]["status"] == "paid"


@pytest.mark.asyncio
async def test_echo_varies_with_arguments():
    async with _demo_session() as session:
        a = await session.call_tool("demo.echo", {"message": "hello", "tag": "a"})
        b = await session.call_tool("demo.echo", {"message": "world", "tag": "b"})
        pa = json.loads(a.content[0].text)
        pb = json.loads(b.content[0].text)
        assert pa != pb
        assert pa["message"] == "hello"
        assert pb["message"] == "world"


@pytest.mark.asyncio
async def test_delete_resource_is_dry_run():
    async with _demo_session() as session:
        result = await session.call_tool(
            "demo.delete_resource",
            {"resource_id": "pod/checkout-1", "resource_type": "pod"},
        )
        payload = json.loads(result.content[0].text)
        assert payload["dry_run"] is True
        assert payload["deleted"] is False
        assert payload["resource_id"] == "pod/checkout-1"


@pytest.mark.asyncio
async def test_extra_tool_env_registers_unknown_action():
    async with _demo_session(extra_tool=True) as session:
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert "demo.unknown_action" in names
