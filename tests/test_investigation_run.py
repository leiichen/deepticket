from __future__ import annotations

import pytest

from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.store import InvestigationRunStore
from deepticket.investigation.transitions import RunTransitionError, validate_transition
from deepticket.layers.storage.local import LocalStorage


@pytest.fixture
def store(tmp_path) -> InvestigationRunStore:
    return InvestigationRunStore(LocalStorage(tmp_path / "data"))


def test_create_run_starts_in_created(store: InvestigationRunStore) -> None:
    run = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    assert run.status == RunStatus.CREATED
    assert run.chat_id == "chat-1"
    loaded = store.get_run("default", run.run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.CREATED


def test_chat_path_created_to_running_to_completed(store: InvestigationRunStore) -> None:
    run = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    running = store.transition("default", run.run_id, RunStatus.RUNNING)
    assert running.status == RunStatus.RUNNING
    assert running.started_at is not None

    completed = store.transition("default", run.run_id, RunStatus.COMPLETED)
    assert completed.status == RunStatus.COMPLETED
    assert completed.finished_at is not None
    assert completed.is_terminal()


def test_ingress_path_created_to_queued_to_running(store: InvestigationRunStore) -> None:
    run = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.INGRESS,
        ingress_job_id="job-1",
    )
    queued = store.transition("default", run.run_id, RunStatus.QUEUED)
    assert queued.status == RunStatus.QUEUED
    running = store.transition("default", run.run_id, RunStatus.RUNNING)
    assert running.status == RunStatus.RUNNING


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (RunStatus.COMPLETED, RunStatus.RUNNING),
        (RunStatus.CREATED, RunStatus.COMPLETED),
        (RunStatus.QUEUED, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunStatus.QUEUED),
    ],
)
def test_invalid_transitions_rejected(from_status: RunStatus, to_status: RunStatus) -> None:
    with pytest.raises(RunTransitionError):
        validate_transition(from_status, to_status)


def test_get_active_run_for_chat(store: InvestigationRunStore) -> None:
    run = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    store.transition("default", run.run_id, RunStatus.RUNNING)
    active = store.get_active_run_for_chat("default", "u1", "chat-1")
    assert active is not None
    assert active.run_id == run.run_id

    store.transition("default", run.run_id, RunStatus.COMPLETED)
    assert store.get_active_run_for_chat("default", "u1", "chat-1") is None


def test_fail_orphaned_runs_marks_non_terminal_as_failed(store: InvestigationRunStore) -> None:
    run = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    store.transition("default", run.run_id, RunStatus.RUNNING)
    count = store.fail_orphaned_runs(reason="service restarted")
    assert count == 1
    loaded = store.get_run("default", run.run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.FAILED
    assert loaded.error_message == "service restarted"


def test_list_runs_for_chat_order(store: InvestigationRunStore) -> None:
    first = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    store.transition("default", first.run_id, RunStatus.RUNNING)
    store.transition("default", first.run_id, RunStatus.COMPLETED)

    second = store.create_run(
        project_id="default",
        uid="u1",
        source=RunSource.CHAT,
        chat_id="chat-1",
    )
    store.transition("default", second.run_id, RunStatus.RUNNING)
    store.transition("default", second.run_id, RunStatus.COMPLETED)

    runs = store.list_runs_for_chat("default", "chat-1", limit=10)
    assert len(runs) == 2
    assert [item.run_id for item in runs] == [second.run_id, first.run_id]
