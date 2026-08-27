"""自定义治理策略示例（可复制到项目里继承改写）。

在 ``service.py`` 注册::

    from deepticket.investigation.policy.examples import AdminBypassDeleteStrategy
    policy_engine = PolicyEngine(
        config.tool_governance,
        extra_strategies=[AdminBypassDeleteStrategy()],
    )
"""
from __future__ import annotations

from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.evaluation import PolicyEvaluation
from deepticket.investigation.policy.strategy import ToolGovernanceStrategy


class AdminBypassDeleteStrategy(ToolGovernanceStrategy):
    """示例：管理员可 override YAML 对 ``demo_delete_resource`` 的 deny。"""

    def evaluate(self, ctx: ToolInvocationContext) -> PolicyEvaluation | None:
        if (
            ctx.tool_name == "demo_delete_resource"
            and ctx.user_is_admin
        ):
            return PolicyEvaluation(
                decision=PolicyDecision.ALLOW,
                reason="admin bypass for demo_delete_resource",
                matched_rule="custom.admin_bypass_delete",
            )
        return None
