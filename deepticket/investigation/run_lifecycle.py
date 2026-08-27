"""InvestigationRun 启动辅助函数。

Chat / Ingress / Ticket 三条入口在真正调 OpenHands 前应统一：
1. ``create_run`` → 2. 写 RUN_CREATED 事件 → 3. transition(RUNNING)
4. 把 ``run_id`` / ``project_id`` 塞进 ``AgentInput``，供引擎写事件与治理 Hook 使用
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from deepticket.investigation.events import RunEventStore
from deepticket.investigation.models import InvestigationRun, RunSource, RunStatus
from deepticket.investigation.store import InvestigationRunStore
from deepticket.layers.input.models import AgentInput

if TYPE_CHECKING:
    # 仅类型检查时 import，避免运行时循环依赖（类似 Java 只在编译期需要的引用）
    from deepticket.service import DeepTicketService


def begin_investigation_run(
    runs: InvestigationRunStore,
    events: RunEventStore,
    *,
    project_id: str,
    uid: str,
    source: RunSource,
    agent_input: AgentInput,
    chat_id: str | None = None,
    ingress_job_id: str | None = None,
    ticket_id: str | None = None,
) -> InvestigationRun:
    run = runs.create_run(
        project_id=project_id,
        uid=uid,
        source=source,
        chat_id=chat_id,
        ingress_job_id=ingress_job_id,
        ticket_id=ticket_id,
    )
    runs.record_run_created_event(project_id, run.run_id, events)
    runs.transition(
        project_id,
        run.run_id,
        RunStatus.RUNNING,
        event_store=events,
    )
    # dataclass 默认可变，直接改字段（无 setter 方法）
    agent_input.run_id = run.run_id
    agent_input.project_id = project_id
    return run


def resolve_system_uid(service: DeepTicketService) -> str:
    """Ingress 等无登录用户场景：用 bootstrap 管理员 uid 作为 Run 归属。"""
    user = service.users.ensure_bootstrap_user(
        service.config.auth.bootstrap_username,
        service.config.auth.bootstrap_password,
    )
    if user is not None:
        return user.uid
    return "system"
