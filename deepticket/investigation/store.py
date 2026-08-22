from __future__ import annotations

import time
import uuid
from datetime import datetime

from deepticket.investigation.models import (
    TERMINAL_RUN_STATUSES,
    InvestigationRun,
    RunSource,
    RunStatus,
)
from deepticket.investigation.transitions import RunTransitionError, validate_transition
from deepticket.layers.storage.base import StorageBackend
from deepticket.utils.time import utc_now_iso

_NS_RUN = "inv_run"
_NS_RUNS_BY_USER = "inv_runs"
_NS_RUNS_BY_CHAT = "inv_runs_chat"
_INDEX_MEMBER = "__index__"


def _score_now() -> float:
    return time.time() * 1000.0


def _score_from_iso(value: str | None) -> float:
    if not value:
        return _score_now()
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).timestamp() * 1000.0
    except ValueError:
        return _score_now()


class InvestigationRunStore:
    """InvestigationRun 持久化（Redis / Local JSON + ZSET 索引）。"""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def create_run(
        self,
        *,
        project_id: str,
        uid: str,
        source: RunSource,
        chat_id: str | None = None,
        ingress_job_id: str | None = None,
        ticket_id: str | None = None,
    ) -> InvestigationRun:
        now = utc_now_iso()
        run = InvestigationRun(
            run_id=uuid.uuid4().hex,
            project_id=project_id,
            uid=uid,
            source=source,
            status=RunStatus.CREATED,
            chat_id=chat_id,
            ingress_job_id=ingress_job_id,
            ticket_id=ticket_id,
            created_at=now,
            updated_at=now,
        )
        self._save(run)
        return run

    def get_run(self, project_id: str, run_id: str) -> InvestigationRun | None:
        doc = self.storage.get_json(_NS_RUN, self._run_key(project_id, run_id))
        if doc is None:
            return None
        return InvestigationRun.from_dict(doc)

    def transition(
        self,
        project_id: str,
        run_id: str,
        to_status: RunStatus,
        *,
        error_message: str | None = None,
        oh_conversation_id: str | None = None,
    ) -> InvestigationRun:
        run = self.get_run(project_id, run_id)
        if run is None:
            raise KeyError(f"investigation run not found: {run_id}")

        validate_transition(run.status, to_status)
        now = utc_now_iso()
        run.status = to_status
        run.updated_at = now

        if to_status == RunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if to_status in TERMINAL_RUN_STATUSES:
            run.finished_at = now
        if error_message:
            run.error_message = error_message[:500]
        elif to_status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
            run.error_message = None
        if oh_conversation_id:
            run.oh_conversation_id = oh_conversation_id

        self._save(run)
        return run

    def set_oh_conversation_id(
        self, project_id: str, run_id: str, oh_conversation_id: str
    ) -> InvestigationRun:
        run = self.get_run(project_id, run_id)
        if run is None:
            raise KeyError(f"investigation run not found: {run_id}")
        run.oh_conversation_id = oh_conversation_id
        run.updated_at = utc_now_iso()
        self._save(run)
        return run

    def list_runs_for_chat(
        self, project_id: str, chat_id: str, *, limit: int = 20
    ) -> list[InvestigationRun]:
        chat_key = self._chat_index_key(project_id, chat_id)
        run_ids = self.storage.zrevrange(_NS_RUNS_BY_CHAT, chat_key, 0, max(0, limit - 1))
        runs: list[InvestigationRun] = []
        for run_id in run_ids:
            run = self.get_run(project_id, run_id)
            if run is not None:
                runs.append(run)
        return runs

    def get_active_run_for_chat(
        self, project_id: str, uid: str, chat_id: str
    ) -> InvestigationRun | None:
        for run in self.list_runs_for_chat(project_id, chat_id, limit=50):
            if run.uid != uid:
                continue
            if not run.is_terminal():
                return run
        return None

    def fail_orphaned_runs(self, *, reason: str) -> int:
        """将非终态 Run 标为 FAILED（进程重启 recovery）。"""
        failed = 0
        for key in self.storage.list_keys(_NS_RUN):
            doc = self.storage.get_json(_NS_RUN, key)
            if not doc:
                continue
            try:
                run = InvestigationRun.from_dict(doc)
            except (KeyError, TypeError, ValueError):
                continue
            if run.is_terminal():
                continue
            try:
                self.transition(
                    run.project_id,
                    run.run_id,
                    RunStatus.FAILED,
                    error_message=reason,
                )
                failed += 1
            except RunTransitionError:
                continue
        return failed

    def _save(self, run: InvestigationRun) -> None:
        doc = run.to_dict()
        self.storage.set_json(_NS_RUN, self._run_key(run.project_id, run.run_id), doc)
        score = _score_from_iso(run.updated_at)
        self.storage.zadd(
            _NS_RUNS_BY_USER,
            self._user_index_key(run.project_id, run.uid),
            {run.run_id: score},
        )
        if run.chat_id:
            self.storage.zadd(
                _NS_RUNS_BY_CHAT,
                self._chat_index_key(run.project_id, run.chat_id),
                {run.run_id: score},
            )

    @staticmethod
    def _run_key(project_id: str, run_id: str) -> str:
        return f"{project_id}:{run_id}"

    @staticmethod
    def _user_index_key(project_id: str, uid: str) -> str:
        return f"{project_id}:{uid}"

    @staticmethod
    def _chat_index_key(project_id: str, chat_id: str) -> str:
        return f"{project_id}:{chat_id}"
