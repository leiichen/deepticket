"""聊天 Run 后台任务管理（SSE 订阅与 InvestigationRun 生命周期）。

Python 异步要点（对比 Java）：
- ``async def`` / ``await`` ≈ CompletableFuture 链，但在单线程事件循环里协作式调度
- ``async for chunk in ...`` + ``yield`` ≈ Java Stream / Reactive Flux 的消费端
- ``asyncio.create_task`` ≈  fire-and-forget 异步任务（类似 ``executor.submit``）
- ``asyncio.Queue``：多个 SSE 订阅者共享同一 Run 的 chunk 广播

一个 chat 同时只允许一个进行中的 Run（内存 ``_runs`` + Redis active run 双重检查）。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from deepticket.investigation.exceptions import PolicyApprovalRequiredError, PolicyDeniedError
from deepticket.investigation.models import RunSource, RunStatus
from deepticket.investigation.run_lifecycle import begin_investigation_run
from deepticket.investigation.transitions import RunTransitionError
from deepticket.layers.input.adapter import InputAdapter
from deepticket.layers.input.models import AgentInput, ChatInput
from deepticket.layers.output.confidence import compute_confidence
from deepticket.layers.output.models import StreamChunk
from deepticket.projects.registry import ProjectContext

logger = logging.getLogger(__name__)

_SENTINEL = object()


@dataclass
class _ChatRun:
    project_id: str
    uid: str
    chat_id: str
    run_id: str | None = None
    agent_conversation_id: str | None = None
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    task: asyncio.Task | None = None
    cancel_requested: bool = False
    done: bool = False


class ChatRunManager:
    """后台执行 Agent；SSE 仅订阅进度，客户端断连不终止任务。

    典型流程：``start()`` → ``asyncio.create_task(_execute)`` → ``subscribe()`` 用 queue 收 chunk。
    """

    def __init__(self, service: object) -> None:
        self._service = service
        self._runs: dict[str, _ChatRun] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(project_id: str, uid: str, chat_id: str) -> str:
        return f"{project_id}:{uid}:{chat_id}"

    async def start(
        self,
        *,
        project: ProjectContext,
        uid: str,
        chat_id: str,
        payload: ChatInput,
        agent_input: AgentInput,
    ) -> _ChatRun:
        key = self._key(project.project_id, uid, chat_id)
        async with self._lock:
            existing = self._runs.get(key)
            if existing is not None and not existing.done:
                raise RuntimeError("该对话已有进行中的 Agent 任务，请稍候")
            active = self._service.investigation_runs.get_active_run_for_chat(
                project.project_id, uid, chat_id
            )
            if active is not None:
                raise RuntimeError("该对话已有进行中的 Agent 任务，请稍候")

            run = _ChatRun(
                project_id=project.project_id,
                uid=uid,
                chat_id=chat_id,
                agent_conversation_id=agent_input.conversation_id,
            )
            self._runs[key] = run

        run.task = asyncio.create_task(
            self._execute(run, project=project, payload=payload, agent_input=agent_input),
            name=f"chat-run:{chat_id}",
        )
        return run

    async def subscribe(self, run: _ChatRun) -> AsyncIterator[StreamChunk]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        run.subscribers.append(queue)
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    break
                assert isinstance(item, StreamChunk)
                yield item
        finally:
            if queue in run.subscribers:
                run.subscribers.remove(queue)

    def is_running(self, project_id: str, uid: str, chat_id: str) -> bool:
        run = self._runs.get(self._key(project_id, uid, chat_id))
        return run is not None and not run.done

    async def cancel_chat(
        self,
        *,
        project_id: str,
        uid: str,
        chat_id: str,
        conversation_id: str | None = None,
    ) -> bool:
        key = self._key(project_id, uid, chat_id)
        run = self._runs.get(key)
        if run is None or run.done:
            conv_id = conversation_id or (run.agent_conversation_id if run else None)
            if conv_id:
                return await self._service.engine.cancel_conversation(conv_id)
            return False

        if run is not None and not run.done and run.run_id:
            try:
                self._service.investigation_runs.transition(
                    project_id,
                    run.run_id,
                    RunStatus.CANCELLED,
                    event_store=self._service.run_events,
                )
            except RunTransitionError as exc:
                logger.warning("InvestigationRun cancel transition skipped: %s", exc)

        run.cancel_requested = True
        conv_id = conversation_id or run.agent_conversation_id
        if conv_id:
            await self._service.engine.cancel_conversation(conv_id)
        if run.task is not None and not run.task.done():
            run.task.cancel()
        return True

    async def resume_after_approval(
        self,
        *,
        project: ProjectContext,
        uid: str,
        chat_id: str,
        run_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> bool:
        """审批后恢复：reject → BLOCKED；approve → 同 run_id 再调 _execute（不新建 Run）。"""
        service = self._service
        project_id = project.project_id
        investigation_run = service.investigation_runs.get_run(project_id, run_id)
        if investigation_run is None:
            raise RuntimeError("Run 不存在")
        if investigation_run.status is not RunStatus.WAITING_APPROVAL:
            raise RuntimeError("Run 不在待审批状态")
        pending = service.approval_requests.get_pending_for_run(project_id, run_id)
        if pending is None:
            raise RuntimeError("未找到待审批请求")

        from deepticket.investigation.approvals import ApprovalStatus

        if not approved:
            service.approval_requests.resolve(
                project_id,
                pending.approval_id,
                status=ApprovalStatus.REJECTED,
                resolved_by=uid,
                reason=reason,
            )
            service.investigation_runs.transition(
                project_id,
                run_id,
                RunStatus.BLOCKED,
                error_message=reason or "审批已拒绝",
                event_store=service.run_events,
            )
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="idle"
            )
            return False

        service.approval_requests.resolve(
            project_id,
            pending.approval_id,
            status=ApprovalStatus.APPROVED,
            resolved_by=uid,
            reason=reason,
        )
        service.approval_requests.issue_tool_grant(
            project_id,
            run_id,
            pending.tool_name,
            approval_id=pending.approval_id,
        )

        thread = service.chat_history.get_thread_summary(project_id, uid, chat_id)
        if thread is None:
            raise RuntimeError(f"聊天不存在: {chat_id}")

        payload = ChatInput(
            message=(
                f"管理员已批准执行工具 {pending.tool_name}，"
                "请继续完成原任务。"
            )
        )
        agent_input = InputAdapter.from_chat(payload)
        service.chat.apply_project_runtime(agent_input, project)
        if thread.get("agent_conversation_id"):
            agent_input.conversation_id = thread["agent_conversation_id"]
        full_thread = service.chat_history.get_thread(project_id, uid, chat_id)
        agent_input.history_messages = service.chat._history_from_thread(
            full_thread,
            current_user_message=payload.message.strip(),
        )
        agent_input.run_id = run_id
        agent_input.project_id = project_id

        key = self._key(project_id, uid, chat_id)
        stale_task: asyncio.Task[None] | None = None
        stale_conv: str | None = None
        async with self._lock:
            existing = self._runs.get(key)
            if existing is not None and not existing.done:
                if existing.run_id != run_id:
                    raise RuntimeError("该对话已有进行中的 Agent 任务，请稍候")
                existing.cancel_requested = True
                stale_task = existing.task
                stale_conv = existing.agent_conversation_id
                self._runs.pop(key, None)
            run = _ChatRun(
                project_id=project_id,
                uid=uid,
                chat_id=chat_id,
                run_id=run_id,
                agent_conversation_id=agent_input.conversation_id,
            )
            self._runs[key] = run

        if stale_conv:
            await service.engine.cancel_conversation(stale_conv)
        if stale_task is not None and not stale_task.done():
            stale_task.cancel()
            try:
                await stale_task
            except asyncio.CancelledError:
                pass

        run.task = asyncio.create_task(
            self._execute(run, project=project, payload=payload, agent_input=agent_input),
            name=f"chat-run-resume:{chat_id}",
        )
        return True

    async def _execute(
        self,
        run: _ChatRun,
        *,
        project: ProjectContext,
        payload: ChatInput,
        agent_input: AgentInput,
    ) -> None:
        """单 chat Run 主循环：建/续 InvestigationRun → 消费 engine 流 → 写终态。"""
        service = self._service
        project_id = run.project_id
        uid = run.uid
        chat_id = run.chat_id

        assistant_parts: list[str] = []
        activity_log: list[dict[str, str]] = []
        agent_conversation_id = agent_input.conversation_id
        confidence: dict | None = None
        policy_denied_message: str | None = None
        if agent_input.run_id:
            investigation_run = service.investigation_runs.get_run(
                project_id, agent_input.run_id
            )
            if investigation_run is None:
                raise RuntimeError(f"InvestigationRun 不存在: {agent_input.run_id}")
            run.run_id = investigation_run.run_id
            if investigation_run.status is RunStatus.WAITING_APPROVAL:
                service.investigation_runs.transition(
                    project_id,
                    investigation_run.run_id,
                    RunStatus.RUNNING,
                    event_store=service.run_events,
                )
        else:
            investigation_run = begin_investigation_run(
                service.investigation_runs,
                service.run_events,
                project_id=project_id,
                uid=uid,
                source=RunSource.CHAT,
                agent_input=agent_input,
                chat_id=chat_id,
            )
            run.run_id = investigation_run.run_id

        agent_input.run_id = run.run_id
        agent_input.metadata["deepticket_uid"] = uid
        agent_input.metadata["deepticket_chat_id"] = chat_id

        try:
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="running"
            )
            async for chunk in service._run_stream(agent_input):
                if run.cancel_requested:
                    break
                if run.run_id:
                    loaded = service.investigation_runs.get_run(project_id, run.run_id)
                    if loaded and loaded.status is RunStatus.WAITING_APPROVAL:
                        service.chat_history.set_agent_run_status(
                            project_id,
                            uid,
                            chat_id,
                            status="waiting_approval",
                            error=loaded.error_message,
                        )
                        return
                if chunk.conversation_id:
                    agent_conversation_id = chunk.conversation_id
                    run.agent_conversation_id = agent_conversation_id
                    if run.run_id:
                        service.investigation_runs.set_oh_conversation_id(
                            project_id, run.run_id, agent_conversation_id
                        )
                if chunk.activity:
                    activity_log.append(
                        {
                            "text": chunk.activity,
                            "kind": chunk.activity_kind or "default",
                        }
                    )
                if chunk.delta:
                    assistant_parts.append(chunk.delta)
                if chunk.policy_denied:
                    policy_denied_message = chunk.policy_message or policy_denied_message
                await self._broadcast(run, chunk)

            if run.cancel_requested:
                if run.run_id:
                    service.investigation_runs.transition(
                        project_id,
                        run.run_id,
                        RunStatus.CANCELLED,
                        event_store=service.run_events,
                    )
                service.chat_history.set_agent_run_status(
                    project_id, uid, chat_id, status="idle"
                )
                return

            reply_text = "".join(assistant_parts)
            confidence = compute_confidence(
                activities=activity_log,
                reply=reply_text,
                ok=True,
                require_analysis=True,
            )
            if confidence:
                await self._broadcast(run, StreamChunk(confidence=confidence))

            if assistant_parts:
                service.chat_history.append_message(
                    project_id,
                    uid,
                    chat_id,
                    role="assistant",
                    content=reply_text,
                    agent_conversation_id=agent_conversation_id,
                    activities=activity_log or None,
                    confidence=confidence if confidence else None,
                    run_id=run.run_id,
                )
            elif agent_conversation_id:
                service.chat_history.set_agent_conversation_id(
                    project_id, uid, chat_id, agent_conversation_id
                )

            if agent_conversation_id:
                try:
                    await service.record_chat_token_usage(
                        project_id=project_id,
                        uid=uid,
                        chat_id=chat_id,
                        agent_conversation_id=agent_conversation_id,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("记录 token 用量失败: %s", exc)
                except RuntimeError as exc:
                    logger.warning("记录 token 用量失败: %s", exc)

            if run.run_id:
                loaded = service.investigation_runs.get_run(project_id, run.run_id)
                if loaded and loaded.status is RunStatus.WAITING_APPROVAL:
                    service.chat_history.set_agent_run_status(
                        project_id,
                        uid,
                        chat_id,
                        status="waiting_approval",
                        error=loaded.error_message,
                    )
                    return
                if loaded and loaded.is_terminal():
                    service.chat_history.set_agent_run_status(
                        project_id,
                        uid,
                        chat_id,
                        status="idle",
                    )
                    return
                service.investigation_runs.transition(
                    project_id,
                    run.run_id,
                    RunStatus.COMPLETED,
                    error_message=policy_denied_message,
                    event_store=service.run_events,
                )
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="idle"
            )
        except asyncio.CancelledError:
            if run.run_id:
                try:
                    service.investigation_runs.transition(
                        project_id,
                        run.run_id,
                        RunStatus.CANCELLED,
                        event_store=service.run_events,
                    )
                except RunTransitionError as exc:
                    logger.warning("InvestigationRun cancel transition skipped: %s", exc)
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="idle"
            )
            raise
        except PolicyApprovalRequiredError as exc:
            logger.info("Run waiting approval: %s", exc)
            if run.run_id:
                try:
                    service.investigation_runs.transition(
                        project_id,
                        run.run_id,
                        RunStatus.WAITING_APPROVAL,
                        error_message=str(exc),
                        event_store=service.run_events,
                    )
                except RunTransitionError as transition_exc:
                    logger.warning(
                        "InvestigationRun waiting_approval transition skipped: %s",
                        transition_exc,
                    )
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="waiting_approval", error=str(exc)
            )
            await self._broadcast(
                run,
                StreamChunk(activity=str(exc), activity_kind="error"),
            )
        except PolicyDeniedError as exc:
            logger.info("Run blocked by policy (legacy hard stop): %s", exc)
            if run.run_id:
                try:
                    service.investigation_runs.transition(
                        project_id,
                        run.run_id,
                        RunStatus.BLOCKED,
                        error_message=str(exc),
                        event_store=service.run_events,
                    )
                except RunTransitionError as transition_exc:
                    logger.warning(
                        "InvestigationRun blocked transition skipped: %s",
                        transition_exc,
                    )
            service.chat_history.set_agent_run_status(
                project_id, uid, chat_id, status="idle", error=str(exc)
            )
            await self._broadcast(
                run,
                StreamChunk(activity=str(exc), activity_kind="error"),
            )
        except Exception as exc:
            logger.exception("Chat run failed: %s", exc)
            if run.run_id:
                try:
                    service.investigation_runs.transition(
                        project_id,
                        run.run_id,
                        RunStatus.FAILED,
                        error_message=str(exc),
                        event_store=service.run_events,
                    )
                except RunTransitionError as transition_exc:
                    logger.warning(
                        "InvestigationRun failed transition skipped: %s",
                        transition_exc,
                    )
            service.chat_history.set_agent_run_status(
                project_id,
                uid,
                chat_id,
                status="failed",
                error=str(exc),
            )
            await self._broadcast(
                run,
                StreamChunk(activity=str(exc), activity_kind="error"),
            )
        finally:
            run.done = True
            await self._broadcast_sentinel(run)
            async with self._lock:
                self._runs.pop(
                    self._key(project_id, uid, chat_id),
                    None,
                )

    async def _broadcast(self, run: _ChatRun, chunk: StreamChunk) -> None:
        for queue in list(run.subscribers):
            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                logger.debug("chat run subscriber queue full, dropping chunk")

    async def _broadcast_sentinel(self, run: _ChatRun) -> None:
        for queue in list(run.subscribers):
            try:
                queue.put_nowait(_SENTINEL)
            except asyncio.QueueFull:
                pass
