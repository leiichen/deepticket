"""OpenHands PreToolUse 硬拦截 + 可插拔策略链。

- **PreToolUse**（``build_hook_config``）：在 OH execute 前同步调用，DENY 时 exit 2 → 工具零调用
- **WebSocket gate**（``_push_event``）：审计 / 兜底，不再作为唯一拦截点

自定义策略：继承 ``ToolGovernanceStrategy``，通过 ``PolicyEngine(extra_strategies=[...])`` 注册。
"""
from __future__ import annotations

import sys

from deepticket.paths import PROJECT_ROOT


def governance_pre_tool_use_command() -> str:
    """返回 OH PreToolUse 可执行命令（绝对路径 shell 包装，避免 venv resolve 丢依赖）。"""
    script = (PROJECT_ROOT / "scripts" / "governance_pre_tool_use.sh").resolve()
    if script.is_file():
        return str(script)
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return f"{venv_python} -m deepticket.investigation.governance.pre_tool_use"
    return f"{sys.executable} -m deepticket.investigation.governance.pre_tool_use"


def default_hook_python_executable() -> str:
    """兼容旧调用：返回 venv python 路径（不 resolve，保留 site-packages）。"""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def build_hook_config(*, python_executable: str | None = None) -> dict[str, object]:
    """返回可写入 POST /api/conversations 的 ``hook_config``。"""
    command = governance_pre_tool_use_command()
    if python_executable and not command.endswith(".sh"):
        command = f"{python_executable} -m deepticket.investigation.governance.pre_tool_use"
    return {
        "pre_tool_use": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 30,
                    }
                ],
            }
        ]
    }


def build_security_analyzer_config() -> dict[str, object]:
    """预留 OH SecurityAnalyzer 配置（当前未使用）。"""
    return {}
