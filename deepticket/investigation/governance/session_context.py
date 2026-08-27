"""OH conversation → DeepTicket 治理上下文（PreToolUse hook 查 Redis）。

PreToolUse 子进程拿不到 HTTP 会话，需在创建 conversation 时写入
``oh_conversation_id → {project_id, run_id, uid, chat_id}`` 映射。
"""
from __future__ import annotations

from dataclasses import dataclass

from deepticket.layers.storage.base import StorageBackend
from deepticket.utils.time import utc_now_iso

_NS_GOV_SESSION = "gov_session"
_NS_GOV_RUN = "gov_run"


@dataclass(frozen=True)
class GovernanceSessionContext:
    project_id: str
    run_id: str
    uid: str
    chat_id: str | None = None
    user_is_admin: bool = False

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "uid": self.uid,
            "chat_id": self.chat_id or "",
            "user_is_admin": "1" if self.user_is_admin else "0",
            "updated_at": utc_now_iso(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> GovernanceSessionContext:
        return cls(
            project_id=str(data.get("project_id") or "default"),
            run_id=str(data.get("run_id") or ""),
            uid=str(data.get("uid") or "unknown"),
            chat_id=data.get("chat_id") or None,
            user_is_admin=str(data.get("user_is_admin") or "0") == "1",
        )


class GovernanceContextStore:
    def __init__(self, storage: StorageBackend) -> None:
        self.storage = storage

    def register(
        self,
        *,
        oh_conversation_id: str,
        project_id: str,
        run_id: str,
        uid: str,
        chat_id: str | None = None,
        user_is_admin: bool = False,
    ) -> None:
        doc = GovernanceSessionContext(
            project_id=project_id,
            run_id=run_id,
            uid=uid,
            chat_id=chat_id,
            user_is_admin=user_is_admin,
        ).to_dict()
        self.storage.set_json(
            _NS_GOV_SESSION,
            oh_conversation_id,
            doc,
        )
        if run_id:
            self.storage.set_json(
                _NS_GOV_RUN,
                f"{project_id}:{run_id}",
                {**doc, "oh_conversation_id": oh_conversation_id},
            )

    def get_by_conversation(self, oh_conversation_id: str) -> GovernanceSessionContext | None:
        doc = self.storage.get_json(_NS_GOV_SESSION, oh_conversation_id)
        if not doc:
            return None
        return GovernanceSessionContext.from_dict(doc)

    def get_by_run(self, project_id: str, run_id: str) -> GovernanceSessionContext | None:
        doc = self.storage.get_json(_NS_GOV_RUN, f"{project_id}:{run_id}")
        if not doc:
            return None
        return GovernanceSessionContext.from_dict(doc)
