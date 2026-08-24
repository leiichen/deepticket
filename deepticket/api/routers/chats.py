from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from deepticket.api.deps import get_service
from deepticket.api.schemas import CreateChatRequest, OkResponse, RenameChatRequest
from deepticket.auth.dependencies import get_current_user
from deepticket.auth.user_store import AuthUser
from deepticket.investigation.models import RunStatus
from deepticket.projects.dependencies import get_project_id

router = APIRouter(prefix="/api/chats", tags=["Chats"])


def _chat_payload(thread: dict) -> dict:
    return {
        "chat_id": thread["chat_id"],
        "project_id": thread.get("project_id"),
        "title": thread["title"],
        "messages": thread.get("messages", []),
        "agent_conversation_id": thread.get("agent_conversation_id"),
        "agent_run_status": thread.get("agent_run_status", "idle"),
        "agent_run_error": thread.get("agent_run_error"),
        "created_at": thread.get("created_at"),
        "updated_at": thread.get("updated_at"),
    }


@router.get("")
async def list_chats(
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return {
        "project_id": project_id,
        "chats": service.chat_history.list_threads(project_id, user.uid),
    }


@router.post("")
async def create_chat(
    body: CreateChatRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    project_id = body.project_id.strip()
    if not service.projects.user_can_access(
        user.uid, project_id, is_admin=service.is_admin(user)
    ):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    thread = service.chat_history.create_thread(
        project_id, user.uid, title=body.title
    )
    return {"chat": _chat_payload(thread)}


@router.get("/{chat_id}")
async def get_chat(
    chat_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    thread = service.chat_history.get_thread(project_id, user.uid, chat_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    return {"chat": _chat_payload(thread)}


@router.get("/{chat_id}/status")
async def get_chat_status(
    chat_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    status = service.chat_history.get_status(project_id, user.uid, chat_id)
    if status is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    active = service.investigation_runs.get_active_run_for_chat(
        project_id, user.uid, chat_id
    )
    if active is not None:
        status["investigation_run"] = active.to_dict()
        if active.status is RunStatus.WAITING_APPROVAL:
            pending = service.approval_requests.get_pending_for_run(
                project_id, active.run_id
            )
            if pending is not None:
                status["pending_approval"] = pending.to_dict()
    recent = service.investigation_runs.list_runs_for_chat(
        project_id, chat_id, limit=5
    )
    status["recent_runs"] = [item.to_dict() for item in recent if item.uid == user.uid]
    return {"status": status}


@router.get("/{chat_id}/runs")
async def list_chat_runs(
    chat_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    service = get_service(request)
    thread = service.chat_history.get_thread_summary(project_id, user.uid, chat_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    runs = service.investigation_runs.list_runs_for_chat(project_id, chat_id, limit=limit)
    return {
        "chat_id": chat_id,
        "runs": [item.to_dict() for item in runs if item.uid == user.uid],
    }


@router.patch("/{chat_id}")
async def rename_chat(
    chat_id: str,
    body: RenameChatRequest,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = get_service(request)
    thread = service.chat_history.rename_thread(
        project_id, user.uid, chat_id, body.title
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    return {"chat": _chat_payload(thread)}


@router.delete("/{chat_id}", response_model=OkResponse)
async def delete_chat(
    chat_id: str,
    request: Request,
    project_id: str = Depends(get_project_id),
    user: AuthUser = Depends(get_current_user),
) -> OkResponse:
    service = get_service(request)
    deleted = service.chat_history.delete_thread(project_id, user.uid, chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="聊天不存在")
    return OkResponse()
