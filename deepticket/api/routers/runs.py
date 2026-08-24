"""Investigation Run REST API（运行详情 / 事件 / 取消 / 审批）。

FastAPI 路由 ≈ Spring ``@RestController``；``Depends(get_current_user)`` ≈ 拦截器鉴权。
审批：``POST .../approve`` / ``reject`` → ``ChatRunManager.resume_after_approval``。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from deepticket.api.deps import get_service
from deepticket.api.schemas import OkResponse
from deepticket.auth.dependencies import get_current_user
from deepticket.auth.user_store import AuthUser
from deepticket.investigation.approvals import ApprovalStatus
from deepticket.investigation.models import RunStatus
from deepticket.investigation.transitions import RunTransitionError
from deepticket.projects.dependencies import get_project_id
from deepticket.projects.registry import ProjectContext

router = APIRouter(prefix="/api/runs", tags=["Investigation Runs"])


class ApprovalActionRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


def _require_run(service, *, project_id: str, user: AuthUser, run_id: str):
    run = service.investigation_runs.get_run(project_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run 不存在")
    if run.uid != user.uid and not service.is_admin(user):
        raise HTTPException(status_code=403, detail="无权访问该 Run")
    return run


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    run = _require_run(service, project_id=project_id, user=user, run_id=run_id)
    pending = service.approval_requests.get_pending_for_run(project_id, run_id)
    return {
        "run": run.to_dict(),
        "pending_approval": pending.to_dict() if pending else None,
    }


@router.get("/{run_id}/events")
async def list_run_events(
    run_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
    after_seq: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    _require_run(service, project_id=project_id, user=user, run_id=run_id)
    events = service.run_events.list_events(
        project_id, run_id, after_seq=after_seq, limit=limit
    )
    return {"run_id": run_id, "events": events, "after_seq": after_seq}


@router.post("/{run_id}/cancel", response_model=OkResponse)
async def cancel_run(
    run_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> OkResponse:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    run = _require_run(service, project_id=project_id, user=user, run_id=run_id)
    if run.is_terminal():
        return OkResponse()
    if run.chat_id:
        await service.chat_runs.cancel_chat(
            project_id=project_id,
            uid=user.uid,
            chat_id=run.chat_id,
            conversation_id=run.oh_conversation_id,
        )
        return OkResponse()
    try:
        service.investigation_runs.transition(
            project_id,
            run_id,
            RunStatus.CANCELLED,
            event_store=service.run_events,
        )
    except RunTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OkResponse()


@router.post("/{run_id}/approve", response_model=OkResponse)
async def approve_run(
    run_id: str,
    request: Request,
    body: ApprovalActionRequest,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> OkResponse:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    run = _require_run(service, project_id=project_id, user=user, run_id=run_id)
    if run.status is not RunStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="Run 不在待审批状态")
    if not run.chat_id:
        pending = service.approval_requests.get_pending_for_run(project_id, run_id)
        if pending is None:
            raise HTTPException(status_code=404, detail="未找到待审批请求")
        service.approval_requests.resolve(
            project_id,
            pending.approval_id,
            status=ApprovalStatus.APPROVED,
            resolved_by=user.uid,
            reason=body.reason.strip() or None,
        )
        service.approval_requests.issue_tool_grant(
            project_id,
            run_id,
            pending.tool_name,
            approval_id=pending.approval_id,
        )
        try:
            service.investigation_runs.transition(
                project_id,
                run_id,
                RunStatus.RUNNING,
                event_store=service.run_events,
            )
        except RunTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return OkResponse()

    project = service.projects.require(project_id)
    try:
        await service.chat_runs.resume_after_approval(
            project=project,
            uid=run.uid,
            chat_id=run.chat_id,
            run_id=run_id,
            approved=True,
            reason=body.reason.strip() or None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OkResponse()


@router.post("/{run_id}/reject", response_model=OkResponse)
async def reject_run(
    run_id: str,
    request: Request,
    body: ApprovalActionRequest,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> OkResponse:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    run = _require_run(service, project_id=project_id, user=user, run_id=run_id)
    if run.status is not RunStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail="Run 不在待审批状态")
    if run.chat_id:
        project: ProjectContext = service.projects.require(project_id)
        try:
            await service.chat_runs.resume_after_approval(
                project=project,
                uid=run.uid,
                chat_id=run.chat_id,
                run_id=run_id,
                approved=False,
                reason=body.reason.strip() or None,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return OkResponse()

    pending = service.approval_requests.get_pending_for_run(project_id, run_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="未找到待审批请求")
    service.approval_requests.resolve(
        project_id,
        pending.approval_id,
        status=ApprovalStatus.REJECTED,
        resolved_by=user.uid,
        reason=body.reason.strip() or None,
    )
    try:
        service.investigation_runs.transition(
            project_id,
            run_id,
            RunStatus.BLOCKED,
            error_message=body.reason.strip() or "审批已拒绝",
            event_store=service.run_events,
        )
    except RunTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OkResponse()
