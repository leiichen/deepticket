"""Investigation Run REST API 自动化测试。"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from deepticket.investigation.events import RunEventType
from deepticket.investigation.models import RunSource, RunStatus
from tests.helpers import auth_headers, login, project_query, seed_completed_run, service


def test_runs_api_requires_auth(client: TestClient) -> None:
    resp = client.get(f"/api/runs/fake-run-id?{project_query()}")
    assert resp.status_code == 401


def test_runs_api_get_run_and_events(client: TestClient) -> None:
    svc = service(client)
    token = login(client, "admin", "admin")
    bootstrap = svc.users.ensure_bootstrap_user("admin", "admin")
    assert bootstrap is not None
    run_id = seed_completed_run(svc, uid=bootstrap.uid)

    headers = auth_headers(token)
    detail = client.get(f"/api/runs/{run_id}?{project_query()}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["run"]["run_id"] == run_id
    assert body["run"]["status"] == "completed"

    events_resp = client.get(
        f"/api/runs/{run_id}/events?{project_query()}&after_seq=0&limit=50",
        headers=headers,
    )
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]
    assert len(events) >= 2
    assert any(item["type"] == RunEventType.RUN_CREATED.value for item in events)
    assert any(item["type"] == RunEventType.TOOL_CALL.value for item in events)


def test_runs_api_isolation_between_users(client: TestClient) -> None:
    svc = service(client)
    login(client, "admin", "admin")
    bootstrap = svc.users.ensure_bootstrap_user("admin", "admin")
    assert bootstrap is not None
    run_id = seed_completed_run(svc, uid=bootstrap.uid)

    username = f"runs_{uuid.uuid4().hex[:8]}"
    password = "pytest-pass-123"
    client.post("/api/auth/register", json={"username": username, "password": password})
    user_token = login(client, username, password)

    resp = client.get(
        f"/api/runs/{run_id}?{project_query()}",
        headers=auth_headers(user_token),
    )
    assert resp.status_code == 403


def test_chat_status_includes_investigation_run(client: TestClient) -> None:
    svc = service(client)
    token = login(client, "admin", "admin")
    bootstrap = svc.users.ensure_bootstrap_user("admin", "admin")
    assert bootstrap is not None
    admin_uid = bootstrap.uid

    thread = svc.chat_history.create_thread("default", admin_uid, title="run-status")
    chat_id = thread["chat_id"]
    run = svc.investigation_runs.create_run(
        project_id="default",
        uid=admin_uid,
        source=RunSource.CHAT,
        chat_id=chat_id,
    )
    svc.investigation_runs.transition(
        "default",
        run.run_id,
        RunStatus.RUNNING,
        event_store=svc.run_events,
    )

    resp = client.get(
        f"/api/chats/{chat_id}/status?{project_query()}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    status = resp.json()["status"]
    assert status["investigation_run"]["run_id"] == run.run_id
    assert status["investigation_run"]["status"] == "running"
    assert isinstance(status.get("recent_runs"), list)


def test_list_chat_runs(client: TestClient) -> None:
    svc = service(client)
    token = login(client, "admin", "admin")
    bootstrap = svc.users.ensure_bootstrap_user("admin", "admin")
    assert bootstrap is not None
    admin_uid = bootstrap.uid
    thread = svc.chat_history.create_thread("default", admin_uid)
    chat_id = thread["chat_id"]
    seed_completed_run(svc, uid=admin_uid, chat_id=chat_id)

    resp = client.get(
        f"/api/chats/{chat_id}/runs?{project_query()}&limit=10",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert len(runs) >= 1
    assert runs[0]["chat_id"] == chat_id
