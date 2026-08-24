from __future__ import annotations

from dataclasses import dataclass

from deepticket.config.tool_governance import PolicyDecision


@dataclass(frozen=True)
class PolicyEvaluation:
    """策略输出：决策 + 人类可读原因 + 命中的规则 id。"""

    decision: PolicyDecision
    reason: str
    matched_rule: str
