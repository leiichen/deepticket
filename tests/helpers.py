"""测试辅助：登录、创建 InvestigationRun 等。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from deepticket.investigation.events import RunEventStore, RunEventType
from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.store import InvestigationRunStore
from deepticket.service import DeepTicketService


def login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def project_query(project_id: str = "default") -> str:
    return f"project_id={project_id}"


def service(client: TestClient) -> DeepTicketService:
    return client.app.state.deepticket.service


def seed_completed_run(
    svc: DeepTicketService,
    *,
    uid: str,
    chat_id: str | None = None,
) -> str:
    runs: InvestigationRunStore = svc.investigation_runs
    events: RunEventStore = svc.run_events
    run = runs.create_run(
        project_id="default",
        uid=uid,
        source=RunSource.CHAT,
        chat_id=chat_id,
    )
    runs.record_run_created_event("default", run.run_id, events)
    runs.transition(
        "default",
        run.run_id,
        RunStatus.RUNNING,
        event_store=events,
    )
    events.append(
        "default",
        run.run_id,
        RunEventType.TOOL_CALL,
        {"tool": "demo_lookup", "mcp_server": "deepticket-demo"},
    )
    runs.transition(
        "default",
        run.run_id,
        RunStatus.COMPLETED,
        event_store=events,
    )
    return run.run_id
