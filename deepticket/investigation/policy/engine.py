"""工具治理策略引擎入口。

``PolicyEngine`` 是对 ``ToolGovernanceEngine`` 的薄封装，默认链末接 YAML 规则。
可通过 ``extra_strategies`` 注入自定义子类（放在 YAML 之前 = 可 override YAML）。
"""
from __future__ import annotations

from deepticket.config.tool_governance import ToolGovernanceConfig
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.evaluation import PolicyEvaluation
from deepticket.investigation.policy.strategy import (
    ToolGovernanceEngine,
    ToolGovernanceStrategy,
    YamlToolGovernanceStrategy,
)

# 向后兼容别名
PolicyContext = ToolInvocationContext

__all__ = [
    "PolicyContext",
    "PolicyEngine",
    "PolicyEvaluation",
    "ToolInvocationContext",
]


class PolicyEngine:
    """可插拔策略链 + YAML 默认规则。"""

    def __init__(
        self,
        config: ToolGovernanceConfig | None = None,
        *,
        extra_strategies: list[ToolGovernanceStrategy] | None = None,
    ) -> None:
        strategies: list[ToolGovernanceStrategy] = list(extra_strategies or [])
        strategies.append(YamlToolGovernanceStrategy(config))
        self._engine = ToolGovernanceEngine(strategies)

    def with_strategies(self, *strategies: ToolGovernanceStrategy) -> PolicyEngine:
        """返回新引擎，在现有链首追加策略（子类 override 用）。"""
        merged = list(strategies) + self._engine._strategies  # noqa: SLF001
        clone = PolicyEngine.__new__(PolicyEngine)
        clone._engine = ToolGovernanceEngine(merged)
        return clone

    def evaluate(self, context: ToolInvocationContext) -> PolicyEvaluation:
        return self._engine.evaluate(context)
