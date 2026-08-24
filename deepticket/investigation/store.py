"""InvestigationRun 持久化（Repository 层）。

存储布局（Redis 为例，Local 用 JSON 文件模拟同样结构）：
- ``inv_run:{project}:{run_id}``     → Run 元数据 JSON
- ``inv_runs:{project}:{uid}``       → ZSET，member=run_id，score=updated_at（按时间倒序列表）
- ``inv_runs_chat:{project}:{chat}`` → 同上，按 chat 索引

Python 提示：
- 方法参数里的 ``*`` 表示其后必须关键字传参，类似 Java 没有直接对应，相当于强制命名参数
- ``| None`` 返回值表示可能查不到（类似 ``Optional``）
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from deepticket.investigation.events import RunEventStore, RunEventType
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
        event_store: RunEventStore | None = None,
    ) -> InvestigationRun:
        """状态迁移唯一入口：校验 → 改字段 → 落库 → 可选写 RunEvent。"""
        run = self.get_run(project_id, run_id)
        if run is None:
            raise KeyError(f"investigation run not found: {run_id}")

        from_status = run.status
        validate_transition(from_status, to_status)
        now = utc_now_iso()
        run.status = to_status
        run.updated_at = now

        if to_status == RunStatus.RUNNING and run.started_at is None:
            run.started_at = now
        if to_status in TERMINAL_RUN_STATUSES:
            run.finished_at = now
        if error_message:
            run.error_message = error_message[:500]
        elif to_status not in {RunStatus.FAILED, RunStatus.BLOCKED, RunStatus.CANCELLED}:
            if not error_message:
                run.error_message = None
        if oh_conversation_id:
            run.oh_conversation_id = oh_conversation_id

        self._save(run)

        if event_store is not None:
            event_store.append(
                project_id,
                run_id,
                RunEventType.RUN_STATUS_CHANGED,
                {"from": from_status.value, "to": to_status.value},
            )
            if to_status in TERMINAL_RUN_STATUSES:
                event_store.append(
                    project_id,
                    run_id,
                    RunEventType.RUN_COMPLETED,
                    {"status": to_status.value},
                )
        return run

    def bump_event_stats(
        self, project_id: str, run_id: str, event_type: RunEventType
    ) -> None:
        """RunEventStore.append 回调：维护冗余计数，供列表 API 展示。"""
        run = self.get_run(project_id, run_id)
        if run is None:
            return
        run.event_count += 1
        if event_type is RunEventType.TOOL_CALL:
            run.tool_call_count += 1
        run.updated_at = utc_now_iso()
        self._save(run)

    def record_run_created_event(
        self, project_id: str, run_id: str, event_store: RunEventStore
    ) -> None:
        run = self.get_run(project_id, run_id)
        if run is None:
            return
        event_store.append(
            project_id,
            run_id,
            RunEventType.RUN_CREATED,
            {
                "source": run.source.value,
                "chat_id": run.chat_id,
                "ingress_job_id": run.ingress_job_id,
            },
        )

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
        """进程重启 recovery：把仍为 RUNNING 等的 Run 标 FAILED（类似宕机后工单清理）。"""
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
        """写主文档 + 更新 ZSET 索引（score 越大越新，zrevrange 取最新）。"""
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
