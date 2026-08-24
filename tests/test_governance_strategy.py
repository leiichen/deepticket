"""PreToolUse hook 与策略链单元测试。"""
from __future__ import annotations

import pytest

from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.governance.pre_tool_use import evaluate_hook_event
from deepticket.investigation.governance.session_context import GovernanceContextStore
from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.policy.context import ToolInvocationContext
from deepticket.investigation.policy.engine import PolicyEngine
from deepticket.investigation.policy.examples import AdminBypassDeleteStrategy
from deepticket.investigation.policy.schema import ToolGovernanceConfig, ToolPolicyRule
from deepticket.layers.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "data")


def test_custom_strategy_overrides_yaml_deny(storage) -> None:
    engine = PolicyEngine(
        ToolGovernanceConfig(
            tools={"demo_delete_resource": ToolPolicyRule(decision=PolicyDecision.DENY)},
        ),
        extra_strategies=[AdminBypassDeleteStrategy()],
    )
    ctx = ToolInvocationContext(
        project_id="default",
        mcp_server="deepticket-demo",
        tool_name="demo_delete_resource",
        arguments={"resource_id": "x"},
        user_is_admin=True,
    )
    result = engine.evaluate(ctx)
    assert result.decision is PolicyDecision.ALLOW
    assert result.matched_rule == "custom.admin_bypass_delete"


def test_yaml_deny_without_override(storage) -> None:
    engine = PolicyEngine(
        ToolGovernanceConfig(
            tools={"demo_delete_resource": ToolPolicyRule(decision=PolicyDecision.DENY)},
        ),
    )
    ctx = ToolInvocationContext(
        project_id="default",
        mcp_server="deepticket-demo",
        tool_name="demo_delete_resource",
        arguments={},
        user_is_admin=False,
    )
    result = engine.evaluate(ctx)
    assert result.decision is PolicyDecision.DENY


def test_governance_session_store_roundtrip(storage) -> None:
    store = GovernanceContextStore(storage)
    store.register(
        oh_conversation_id="conv-1",
        project_id="default",
        run_id="run-1",
        uid="u1",
        chat_id="c1",
        user_is_admin=True,
    )
    loaded = store.get_by_conversation("conv-1")
    assert loaded is not None
    assert loaded.run_id == "run-1"
    assert loaded.uid == "u1"
    assert loaded.user_is_admin is True


def test_pre_tool_use_hook_denies_delete(monkeypatch, storage) -> None:
    from deepticket.investigation.events import RunEventStore
    from deepticket.investigation.governance import pre_tool_use as hook_mod
    from deepticket.investigation.governance.gate import ToolGovernanceGate
    from deepticket.investigation.store import InvestigationRunStore

    runs = InvestigationRunStore(storage)
    events = RunEventStore(storage, run_store=runs)
    run = runs.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
    )
    runs.transition("default", run.run_id, RunStatus.RUNNING, event_store=events)
    gate = ToolGovernanceGate(
        PolicyEngine(
            ToolGovernanceConfig(
                tools={
                    "demo_delete_resource": ToolPolicyRule(decision=PolicyDecision.DENY),
                }
            )
        ),
        events,
    )
    sessions = GovernanceContextStore(storage)
    sessions.register(
        oh_conversation_id="sess-1",
        project_id="default",
        run_id=run.run_id,
        uid="u1",
    )
    monkeypatch.setattr(
        hook_mod,
        "_build_stack",
        lambda: (gate, sessions, events, storage),
    )

    allow, message = evaluate_hook_event(
        {
            "event_type": "PreToolUse",
            "tool_name": "demo_delete_resource",
            "tool_input": {"data": {"resource_id": "order-1"}},
            "session_id": "sess-1",
        }
    )
    assert allow is False
    assert "denied" in message.lower()
