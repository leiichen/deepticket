from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from deepticket.layers.storage.base import StorageBackend
from deepticket.utils.time import utc_now_iso

logger = logging.getLogger(__name__)

_NS_MCP_TOOLS = "mcp_tools"


@dataclass(frozen=True)
class ToolDescriptor:
    server_id: str
    name: str
    description: str = ""


class McpToolRegistry:
    """缓存 MCP tools/list 结果（Admin 保存 MCP 时刷新）。"""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def get_tools(self, project_id: str, server_id: str) -> list[ToolDescriptor]:
        doc = self.storage.get_json(_NS_MCP_TOOLS, self._key(project_id, server_id))
        if not doc:
            return []
        tools: list[ToolDescriptor] = []
        for item in doc.get("tools") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            tools.append(
                ToolDescriptor(
                    server_id=server_id,
                    name=name,
                    description=str(item.get("description") or ""),
                )
            )
        return tools

    def list_cached_servers(self, project_id: str) -> list[str]:
        prefix = f"{project_id}:"
        servers: list[str] = []
        for key in self.storage.list_keys(_NS_MCP_TOOLS):
            if key.startswith(prefix):
                servers.append(key[len(prefix) :])
        return sorted(servers)

    async def refresh_server(
        self,
        project_id: str,
        server_id: str,
        server_config: dict[str, Any],
        *,
        repo_root: Path | None = None,
    ) -> list[ToolDescriptor]:
        if str(server_config.get("transport") or "").strip() != "stdio":
            logger.info("跳过非 stdio MCP registry 刷新: %s", server_id)
            return []
        command = str(server_config.get("command") or "").strip()
        if not command:
            logger.warning("MCP %s 缺少 command，跳过 tools/list", server_id)
            return []
        args = [str(item) for item in server_config.get("args") or []]
        cwd = server_config.get("cwd")
        if cwd:
            workdir = str(cwd)
        elif repo_root is not None:
            workdir = str(repo_root)
        else:
            workdir = None

        params = StdioServerParameters(
            command=command,
            args=args,
            cwd=workdir,
        )
        tools: list[ToolDescriptor] = []
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    for tool in result.tools:
                        tools.append(
                            ToolDescriptor(
                                server_id=server_id,
                                name=tool.name,
                                description=tool.description or "",
                            )
                        )
        except (TimeoutError, OSError, RuntimeError) as exc:
            logger.warning("MCP tools/list 失败 (%s/%s): %s", project_id, server_id, exc)
            return []

        self.storage.set_json(
            _NS_MCP_TOOLS,
            self._key(project_id, server_id),
            {
                "project_id": project_id,
                "server_id": server_id,
                "updated_at": utc_now_iso(),
                "tools": [
                    {
                        "name": item.name,
                        "description": item.description,
                    }
                    for item in tools
                ],
            },
        )
        return tools

    async def refresh_project_servers(
        self,
        project_id: str,
        servers: dict[str, dict[str, Any]],
        *,
        repo_root: Path | None = None,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for server_id, cfg in servers.items():
            if cfg.get("enabled") is False:
                self.storage.delete(_NS_MCP_TOOLS, self._key(project_id, server_id))
                continue
            tools = await self.refresh_server(
                project_id,
                server_id,
                cfg,
                repo_root=repo_root,
            )
            counts[server_id] = len(tools)
        return counts

    @staticmethod
    def _key(project_id: str, server_id: str) -> str:
        return f"{project_id}:{server_id}"
