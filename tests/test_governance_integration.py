"""治理基础设施：Hook 配置、OH payload、事件映射、审批、生命周期。"""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from deepticket.config.schema import EngineConfig
from deepticket.config.tool_governance import PolicyDecision
from deepticket.investigation.approvals import ApprovalRequestStore, ApprovalStatus
from deepticket.investigation.event_mapper import extract_mcp_tool_call, map_openhands_event
from deepticket.investigation.events import RunEventType
from deepticket.investigation.governance.hook import (
    build_hook_config,
    governance_pre_tool_use_command,
)
from deepticket.investigation.governance.pre_tool_use import evaluate_hook_event
from deepticket.investigation.governance.session_context import GovernanceContextStore
from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.run_lifecycle import begin_investigation_run
from deepticket.layers.engine.openhands_engine import OpenHandsEngine
from deepticket.layers.input.models import AgentInput
from deepticket.layers.storage.local import LocalStorage
from deepticket.paths import PROJECT_ROOT


def test_hook_config_uses_project_venv_wrapper() -> None:
    config = build_hook_config()
    command = config["pre_tool_use"][0]["hooks"][0]["command"]
    assert "governance_pre_tool_use" in command
    script = PROJECT_ROOT / "scripts" / "governance_pre_tool_use.sh"
    if script.is_file():
        assert str(script) in command or command.endswith(".sh")


def test_governance_shell_wrapper_exits_2_on_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    script = PROJECT_ROOT / "scripts" / "governance_pre_tool_use.sh"
    if not script.is_file():
        pytest.skip("governance_pre_tool_use.sh not present")
    config_path = PROJECT_ROOT / "deepticket.yaml"
    if not config_path.is_file():
        pytest.skip("deepticket.yaml not present")
    monkeypatch.setenv("DEEPTICKET_CONFIG", str(config_path))
    proc = subprocess.run(
        [str(script)],
        input=json.dumps(
            {
                "tool_name": "demo_delete_resource",
                "tool_input": {"data": {"resource_id": "x"}},
                "session_id": "missing-session",
            }
        ),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ},
    )
    assert proc.returncode == 2
    assert "denied" in proc.stderr.lower() or "blocked" in proc.stderr.lower()


def test_conversation_payload_omits_invalid_oh_tags() -> None:
    engine = OpenHandsEngine(
        EngineConfig(),
        llm_model="test",
        llm_api_key="k",
        llm_base_url="http://127.0.0.1:1",
        workspace_dir="/tmp",
    )
    engine.governance_hook_config = build_hook_config()
    agent_input = AgentInput(
        prompt="hi",
        project_id="default",
        run_id="run-abc",
        metadata={
            "deepticket_uid": "u1",
            "deepticket_chat_id": "c1",
        },
    )
    payload = engine._conversation_governance_payload(agent_input)
    assert "hook_config" in payload
    assert "tags" not in payload
    for key in payload.get("tags", {}):
        assert key.isalnum() and key.islower()


def test_extract_mcp_tool_call_demo_tools() -> None:
    event = {
        "kind": "ActionEvent",
        "action": {
            "tool_name": "demo_lookup",
            "arguments": {"key": "order-1"},
        },
    }
    parsed = extract_mcp_tool_call(event)
    assert parsed == ("deepticket-demo", "demo_lookup", {"key": "order-1"})


def test_map_openhands_action_to_tool_call_event() -> None:
    event = {
        "kind": "ActionEvent",
        "action": {"tool_name": "demo_echo", "arguments": {"msg": "hi"}},
    }
    mapped = map_openhands_event(event)
    assert mapped is not None
    event_type, payload = mapped
    assert event_type is RunEventType.TOOL_CALL
    assert payload["tool"] == "demo_echo"


def test_approval_store_resolve(tmp_path) -> None:
    storage = LocalStorage(str(tmp_path / "data"))
    store = ApprovalRequestStore(storage)
    req = store.create(
        project_id="default",
        run_id="run-1",
        tool_name="demo_exec_command",
        mcp_server="deepticket-demo",
        arguments={"command": "ls"},
    )
    loaded = store.get_pending_for_run("default", "run-1")
    assert loaded is not None
    assert loaded.approval_id == req.approval_id

    store.resolve(
        "default",
        req.approval_id,
        status=ApprovalStatus.REJECTED,
        resolved_by="admin",
        reason="no",
    )
    assert store.get_pending_for_run("default", "run-1") is None


def test_begin_investigation_run_sets_agent_input(tmp_path) -> None:
    from deepticket.investigation.events import RunEventStore
    from deepticket.investigation.store import InvestigationRunStore

    storage = LocalStorage(str(tmp_path / "data"))
    runs = InvestigationRunStore(storage)
    events = RunEventStore(storage, run_store=runs)
    agent_input = AgentInput(prompt="question")
    run = begin_investigation_run(
        runs,
        events,
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        agent_input=agent_input,
        chat_id="c1",
    )
    assert agent_input.run_id == run.run_id
    assert agent_input.project_id == "default"
    loaded = runs.get_run("default", run.run_id)
    assert loaded is not None
    assert loaded.status is RunStatus.RUNNING


def test_governance_context_lookup_by_conversation(tmp_path) -> None:
    storage = LocalStorage(str(tmp_path / "data"))
    store = GovernanceContextStore(storage)
    store.register(
        oh_conversation_id="oh-conv-1",
        project_id="default",
        run_id="run-xyz",
        uid="u1",
        chat_id="c1",
        user_is_admin=True,
    )
    ctx = store.get_by_conversation("oh-conv-1")
    assert ctx is not None
    assert ctx.run_id == "run-xyz"
    assert ctx.user_is_admin is True


def test_evaluate_hook_event_allow_lookup(tmp_path, monkeypatch) -> None:
    from deepticket.investigation.events import RunEventStore
    from deepticket.investigation.governance import pre_tool_use as hook_mod
    from deepticket.investigation.governance.gate import ToolGovernanceGate
    from deepticket.investigation.policy.engine import PolicyEngine
    from deepticket.investigation.policy.schema import ToolGovernanceConfig, ToolPolicyRule
    from deepticket.investigation.store import InvestigationRunStore

    storage = LocalStorage(str(tmp_path / "data"))
    runs = InvestigationRunStore(storage)
    events = RunEventStore(storage, run_store=runs)
    gate = ToolGovernanceGate(
        PolicyEngine(
            ToolGovernanceConfig(
                tools={"demo_lookup": ToolPolicyRule(decision=PolicyDecision.ALLOW)},
            )
        ),
        events,
    )
    sessions = GovernanceContextStore(storage)
    run = runs.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
    )
    runs.transition("default", run.run_id, RunStatus.RUNNING, event_store=events)
    sessions.register(
        oh_conversation_id="sess-allow",
        project_id="default",
        run_id=run.run_id,
        uid="u1",
    )
    monkeypatch.setattr(hook_mod, "_build_stack", lambda: (gate, sessions, events, storage))

    allow, message = evaluate_hook_event(
        {
            "tool_name": "demo_lookup",
            "tool_input": {"data": {"key": "x"}},
            "session_id": "sess-allow",
        }
    )
    assert allow is True
    assert message == ""
