"""ToolGovernanceGate 单元测试：allow / deny / require_approval + RunEvent。"""
from __future__ import annotations

import pytest

from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.approvals import ApprovalRequestStore, ApprovalStatus
from deepticket.investigation.events import RunEventStore, RunEventType
from deepticket.investigation.governance.gate import ToolGovernanceGate
from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.policy.engine import PolicyEngine
from deepticket.investigation.policy.schema import ToolGovernanceConfig, ToolPolicyRule
from deepticket.investigation.store import InvestigationRunStore
from deepticket.layers.storage.local import LocalStorage


@pytest.fixture
def governance_stack(tmp_path):
    storage = LocalStorage(str(tmp_path / "data"))
    runs = InvestigationRunStore(storage)
    events = RunEventStore(storage, run_store=runs)
    approvals = ApprovalRequestStore(storage)
    config = ToolGovernanceConfig(
        tools={
            "demo_delete_resource": ToolPolicyRule(decision=PolicyDecision.DENY),
            "demo_exec_command": ToolPolicyRule(decision=PolicyDecision.REQUIRE_APPROVAL),
            "demo_lookup": ToolPolicyRule(decision=PolicyDecision.ALLOW),
        }
    )
    gate = ToolGovernanceGate(
        PolicyEngine(config),
        events,
        approval_store=approvals,
    )
    run = runs.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="c1",
    )
    runs.transition("default", run.run_id, RunStatus.RUNNING, event_store=events)
    return gate, events, approvals, run.run_id


def test_gate_allow_no_block_events(governance_stack) -> None:
    gate, events, _approvals, run_id = governance_stack
    result = gate.evaluate_mcp_tool(
        project_id="default",
        run_id=run_id,
        mcp_server="deepticket-demo",
        tool_name="demo_lookup",
        arguments={"key": "order-1"},
        uid="u1",
    )
    assert result.blocked is False
    assert result.evaluation.decision is PolicyDecision.ALLOW
    audit = events.list_events("default", run_id)
    assert any(item["type"] == RunEventType.POLICY_DECISION.value for item in audit)
    assert not any(item["type"] == RunEventType.ERROR.value for item in audit)


def test_gate_deny_hard_block(governance_stack) -> None:
    gate, events, _approvals, run_id = governance_stack
    result = gate.evaluate_mcp_tool(
        project_id="default",
        run_id=run_id,
        mcp_server="deepticket-demo",
        tool_name="demo_delete_resource",
        arguments={"resource_id": "pod/x"},
        uid="u1",
    )
    assert result.blocked is True
    assert result.hard_block is True
    assert result.waiting_approval is False
    assert result.evaluation.decision is PolicyDecision.DENY
    audit = events.list_events("default", run_id)
    deny = next(
        item for item in audit if item["type"] == RunEventType.POLICY_DECISION.value
    )
    assert deny["payload"]["decision"] == "deny"
    assert any(
        item["type"] == RunEventType.ERROR.value
        and item["payload"].get("code") == "policy_denied"
        for item in audit
    )


def test_gate_tool_grant_allows_after_approval(governance_stack) -> None:
    gate, events, approvals, run_id = governance_stack
    approvals.issue_tool_grant("default", run_id, "demo_exec_command", approval_id="ap-1")
    result = gate.evaluate_mcp_tool(
        project_id="default",
        run_id=run_id,
        mcp_server="deepticket-demo",
        tool_name="demo_exec_command",
        arguments={"command": "ls"},
        uid="u1",
    )
    assert result.blocked is False
    assert result.evaluation.decision is PolicyDecision.ALLOW
    assert result.evaluation.matched_rule == "approval.grant"
    # 一次性许可：第二次仍需要审批
    result2 = gate.evaluate_mcp_tool(
        project_id="default",
        run_id=run_id,
        mcp_server="deepticket-demo",
        tool_name="demo_exec_command",
        arguments={"command": "ls"},
        uid="u1",
    )
    assert result2.waiting_approval is True


def test_mark_run_waiting_approval(tmp_path) -> None:
    from deepticket.investigation.governance.approval_pause import mark_run_waiting_approval
    from deepticket.layers.storage.chat_history import ChatHistoryStore

    storage = LocalStorage(str(tmp_path / "data"))
    runs = InvestigationRunStore(storage)
    events = RunEventStore(storage, run_store=runs)
    chats = ChatHistoryStore(storage)
    thread = chats.create_thread("default", "u1", title="approval-test")
    chat_id = thread["chat_id"]
    run = runs.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id=chat_id,
    )
    runs.transition("default", run.run_id, RunStatus.RUNNING, event_store=events)
    mark_run_waiting_approval(
        storage,
        project_id="default",
        run_id=run.run_id,
        uid="u1",
        chat_id=chat_id,
        message="needs approval",
        event_store=events,
    )
    loaded = runs.get_run("default", run.run_id)
    assert loaded is not None
    assert loaded.status is RunStatus.WAITING_APPROVAL
    status = chats.get_status("default", "u1", chat_id)
    assert status is not None
    assert status["agent_run_status"] == "waiting_approval"


def test_gate_require_approval_creates_pending(governance_stack) -> None:
    gate, events, approvals, run_id = governance_stack
    result = gate.evaluate_mcp_tool(
        project_id="default",
        run_id=run_id,
        mcp_server="deepticket-demo",
        tool_name="demo_exec_command",
        arguments={"command": "ls"},
        uid="u1",
    )
    assert result.blocked is True
    assert result.waiting_approval is True
    assert result.approval_id
    pending = approvals.get_pending_for_run("default", run_id)
    assert pending is not None
    assert pending.tool_name == "demo_exec_command"
    assert pending.status is ApprovalStatus.PENDING
