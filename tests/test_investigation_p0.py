from __future__ import annotations

import pytest

from deepticket.investigation.events import RunEventStore, RunEventType
from deepticket.investigation.models import RunSource
from deepticket.investigation.policy.engine import PolicyContext, PolicyEngine
from deepticket.investigation.policy.schema import (
    PolicyDecision,
    ToolGovernanceConfig,
    ToolPolicyRule,
)
from deepticket.layers.storage.local import LocalStorage


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "data")


def test_policy_engine_tool_rule_overrides_global(storage) -> None:
    engine = PolicyEngine(
        ToolGovernanceConfig(
            tools={
                "demo_delete_resource": ToolPolicyRule(decision=PolicyDecision.DENY),
            }
        )
    )
    result = engine.evaluate(
        PolicyContext(
            project_id="default",
            mcp_server="deepticket-demo",
            tool_name="demo_delete_resource",
            arguments={"resource_id": "x"},
        )
    )
    assert result.decision is PolicyDecision.DENY
    assert result.matched_rule == "tools.demo_delete_resource"


def test_run_event_store_append_and_list(storage) -> None:
    from deepticket.investigation.store import InvestigationRunStore

    runs = InvestigationRunStore(storage)
    store = RunEventStore(storage, run_store=runs)
    run = runs.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="c1",
    )
    first = store.append("default", run.run_id, RunEventType.RUN_CREATED, {"source": "chat"})
    second = store.append(
        "default",
        run.run_id,
        RunEventType.TOOL_CALL,
        {"tool": "demo_lookup"},
    )
    events = store.list_events("default", run.run_id)
    loaded = runs.get_run("default", run.run_id)
    assert loaded is not None
    assert loaded.event_count == 2
    assert loaded.tool_call_count == 1
    assert len(events) == 2
    assert int(first["seq"]) == 1
    assert int(second["seq"]) == 2
    assert store.list_events("default", run.run_id, after_seq=1) == [second]


def test_policy_engine_unknown_tool_deny(storage) -> None:
    engine = PolicyEngine(
        ToolGovernanceConfig(
            global_={"default": "allow", "unknown_tool_mode": "deny"},
        )
    )
    result = engine.evaluate(
        PolicyContext(
            project_id="default",
            mcp_server="deepticket-demo",
            tool_name="demo_unknown_action",
            arguments={},
            tool_known=False,
        )
    )
    assert result.decision is PolicyDecision.DENY
