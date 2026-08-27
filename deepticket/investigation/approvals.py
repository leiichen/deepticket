"""工具审批单持久化（require_approval 策略命中时创建）。

流程：
1. ToolGovernanceGate 创建 PENDING 审批单
2. Run → waiting_approval，前端「运行详情」展示 Approve/Reject
3. POST /api/runs/{id}/approve 或 reject → ChatRunManager.resume_after_approval()

存储：与 Run 类似，主键 JSON + 按 run_id 的 ZSET 索引。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from deepticket.layers.storage.base import StorageBackend
from deepticket.utils.time import utc_now_iso

_NS_APPROVAL = "inv_approval"
_NS_APPROVALS_BY_RUN = "inv_approvals_run"
_NS_APPROVAL_GRANT = "inv_approval_grant"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    approval_id: str
    project_id: str
    run_id: str
    tool_name: str
    mcp_server: str
    arguments: dict[str, Any]
    status: ApprovalStatus
    created_at: str
    resolved_at: str | None = None
    resolved_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "tool_name": self.tool_name,
            "mcp_server": self.mcp_server,
            "arguments": self.arguments,
            "status": self.status.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        return cls(
            approval_id=str(data["approval_id"]),
            project_id=str(data["project_id"]),
            run_id=str(data["run_id"]),
            tool_name=str(data["tool_name"]),
            mcp_server=str(data.get("mcp_server") or ""),
            arguments=dict(data.get("arguments") or {}),
            status=ApprovalStatus(str(data["status"])),
            created_at=str(data["created_at"]),
            resolved_at=data.get("resolved_at") or None,
            resolved_by=data.get("resolved_by") or None,
            reason=data.get("reason") or None,
        )


class ApprovalRequestStore:
    """审批 CRUD；resolve 时更新 status 并记录 resolved_by / reason。"""

    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def create(
        self,
        *,
        project_id: str,
        run_id: str,
        tool_name: str,
        mcp_server: str,
        arguments: dict[str, Any],
    ) -> ApprovalRequest:
        now = utc_now_iso()
        request = ApprovalRequest(
            approval_id=uuid.uuid4().hex,
            project_id=project_id,
            run_id=run_id,
            tool_name=tool_name,
            mcp_server=mcp_server,
            arguments=arguments,
            status=ApprovalStatus.PENDING,
            created_at=now,
        )
        self._save(request)
        return request

    def get(self, project_id: str, approval_id: str) -> ApprovalRequest | None:
        doc = self.storage.get_json(_NS_APPROVAL, self._key(project_id, approval_id))
        if doc is None:
            return None
        return ApprovalRequest.from_dict(doc)

    def get_pending_for_run(
        self, project_id: str, run_id: str
    ) -> ApprovalRequest | None:
        approval_ids = self.storage.zrevrange(
            _NS_APPROVALS_BY_RUN, self._run_key(project_id, run_id), 0, 20
        )
        for approval_id in approval_ids:
            request = self.get(project_id, approval_id)
            if request is None:
                continue
            if request.status is ApprovalStatus.PENDING:
                return request
        return None

    def resolve(
        self,
        project_id: str,
        approval_id: str,
        *,
        status: ApprovalStatus,
        resolved_by: str,
        reason: str | None = None,
    ) -> ApprovalRequest:
        request = self.get(project_id, approval_id)
        if request is None:
            raise KeyError(f"approval not found: {approval_id}")
        if request.status is not ApprovalStatus.PENDING:
            raise ValueError(f"approval already resolved: {request.status.value}")
        request.status = status
        request.resolved_at = utc_now_iso()
        request.resolved_by = resolved_by
        request.reason = reason
        self._save(request)
        return request

    def issue_tool_grant(
        self,
        project_id: str,
        run_id: str,
        tool_name: str,
        *,
        approval_id: str,
    ) -> None:
        """批准后发放一次性工具执行许可（PreToolUse 消费后删除）。"""
        self.storage.set_json(
            _NS_APPROVAL_GRANT,
            self._grant_key(project_id, run_id, tool_name),
            {
                "approval_id": approval_id,
                "run_id": run_id,
                "tool_name": tool_name,
                "issued_at": utc_now_iso(),
            },
        )

    def consume_tool_grant(
        self, project_id: str, run_id: str, tool_name: str
    ) -> bool:
        """若存在未消费的批准许可则删除并返回 True。"""
        key = self._grant_key(project_id, run_id, tool_name)
        doc = self.storage.get_json(_NS_APPROVAL_GRANT, key)
        if doc is None:
            return False
        self.storage.delete(_NS_APPROVAL_GRANT, key)
        return True

    def _save(self, request: ApprovalRequest) -> None:
        self.storage.set_json(
            _NS_APPROVAL,
            self._key(request.project_id, request.approval_id),
            request.to_dict(),
        )
        self.storage.zadd(
            _NS_APPROVALS_BY_RUN,
            self._run_key(request.project_id, request.run_id),
            {request.approval_id: float(len(request.created_at))},
        )

    @staticmethod
    def _key(project_id: str, approval_id: str) -> str:
        return f"{project_id}:{approval_id}"

    @staticmethod
    def _run_key(project_id: str, run_id: str) -> str:
        return f"{project_id}:{run_id}"

    @staticmethod
    def _grant_key(project_id: str, run_id: str, tool_name: str) -> str:
        return f"{project_id}:{run_id}:{tool_name}"
