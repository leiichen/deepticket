"""可继承 / 可组合的工具治理策略（Python 正常用法：ABC + 责任链）。

用法示例::

    class MyStrategy(ToolGovernanceStrategy):
        def evaluate(self, ctx: ToolInvocationContext) -> PolicyEvaluation | None:
            if ctx.uid == "vip" and ctx.tool_name == "demo_delete_resource":
                return PolicyEvaluation(ALLOW, "vip override", "custom.vip")
            return None  # 交给下一个策略

    engine = ToolGovernanceEngine([
        MyStrategy(),
        YamlToolGovernanceStrategy(config),
    ])
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from deepticket.config.tool_governance import PolicyDecision, ToolGovernanceConfig
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.evaluation import PolicyEvaluation


class ToolGovernanceStrategy(ABC):
    """策略基类：返回 ``PolicyEvaluation`` 表示命中；返回 ``None`` 交给链上下一个。"""

    @abstractmethod
    def evaluate(self, ctx: ToolInvocationContext) -> PolicyEvaluation | None:
        raise NotImplementedError


class YamlToolGovernanceStrategy(ToolGovernanceStrategy):
    """YAML 三级规则（tools / mcp / global），链末默认策略。"""

    def __init__(self, config: ToolGovernanceConfig | None = None) -> None:
        self._config = config or ToolGovernanceConfig()

    def evaluate(self, ctx: ToolInvocationContext) -> PolicyEvaluation | None:
        tool_key = ctx.tool_name.strip()
        if tool_key in self._config.tools:
            rule = self._config.tools[tool_key]
            return PolicyEvaluation(
                decision=rule.decision,
                reason=f"matched tools.{tool_key}",
                matched_rule=f"tools.{tool_key}",
            )

        server = ctx.mcp_server.strip()
        if server and server in self._config.mcp:
            rule = self._config.mcp[server]
            if not ctx.tool_known:
                unknown = self._unknown_tool_decision(rule.unknown_tool_mode, server)
                if unknown is not None:
                    return unknown
            return PolicyEvaluation(
                decision=rule.default,
                reason=f"matched mcp.{server}.default",
                matched_rule=f"mcp.{server}.default",
            )

        if not ctx.tool_known:
            unknown = self._unknown_tool_decision(
                self._config.global_.unknown_tool_mode,
                server or "global",
            )
            if unknown is not None:
                return unknown

        default = self._config.global_.default
        return PolicyEvaluation(
            decision=default,
            reason="matched global.default",
            matched_rule="global.default",
        )

    @staticmethod
    def _unknown_tool_decision(
        mode: str,
        scope: str,
    ) -> PolicyEvaluation | None:
        if mode == "allow":
            return None
        if mode == "deny":
            return PolicyEvaluation(
                decision=PolicyDecision.DENY,
                reason=f"unknown tool blocked ({scope})",
                matched_rule=f"unknown_tool.{scope}",
            )
        return PolicyEvaluation(
            decision=PolicyDecision.ALLOW,
            reason=f"unknown tool audited ({scope})",
            matched_rule=f"unknown_tool.audit.{scope}",
        )


class ToolGovernanceEngine:
    """按顺序执行策略链；全部返回 None 时默认 ALLOW。"""

    def __init__(self, strategies: Sequence[ToolGovernanceStrategy]) -> None:
        self._strategies = list(strategies)

    def evaluate(self, ctx: ToolInvocationContext) -> PolicyEvaluation:
        for strategy in self._strategies:
            result = strategy.evaluate(ctx)
            if result is not None:
                return result
        return PolicyEvaluation(
            decision=PolicyDecision.ALLOW,
            reason="no strategy matched; default allow",
            matched_rule="default.allow",
        )
