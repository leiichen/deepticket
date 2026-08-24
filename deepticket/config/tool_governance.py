"""工具治理 YAML 配置模型（Pydantic）。

``deepticket.yaml`` 片段示例::

    tool_governance:
      global:
        default: allow
      tools:
        demo_delete_resource:
          decision: deny
        demo_exec_command:
          decision: require_approval

Pydantic ``BaseModel`` ≈ Java Bean + 校验；``Field(alias="global")`` 映射 YAML 键 ``global``。
``PolicyDecision`` 三值：allow / deny / require_approval。
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


UnknownToolMode = Literal["allow", "audit", "deny"]


class ToolPolicyRule(BaseModel):
    decision: PolicyDecision


class McpGovernanceRule(BaseModel):
    default: PolicyDecision = PolicyDecision.ALLOW
    unknown_tool_mode: UnknownToolMode = "audit"


class GlobalGovernanceRule(BaseModel):
    default: PolicyDecision = PolicyDecision.ALLOW
    unknown_tool_mode: UnknownToolMode = "audit"


class ToolGovernanceConfig(BaseModel):
    global_: GlobalGovernanceRule = Field(
        default_factory=GlobalGovernanceRule,
        alias="global",
    )
    mcp: dict[str, McpGovernanceRule] = Field(default_factory=dict)
    tools: dict[str, ToolPolicyRule] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}
