from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    chat_id: str = Field(min_length=1)
    conversation_id: str | None = None
    image_urls: list[str] = Field(default_factory=list)


class CreateChatRequest(BaseModel):
    title: str = Field(default="新会话", max_length=48)
    project_id: str = Field(default="default", min_length=1, max_length=64)


class ProjectMemberRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)


class ProjectConfigRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)
    enabled: bool = True
    knowledge: dict = Field(default_factory=dict)
    mcp: dict = Field(default_factory=dict)
    extensions: dict = Field(default_factory=dict)


class ProjectMetaPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    enabled: bool | None = None


class ProjectKnowledgePatchRequest(BaseModel):
    repos: list[dict] = Field(default_factory=list)


class ProjectMcpPatchRequest(BaseModel):
    servers: dict = Field(default_factory=dict)


class ProjectExtensionsPatchRequest(BaseModel):
    user_skills_dir: str | None = None
    agents_md: str | None = None


class ProjectMembersUpdateRequest(BaseModel):
    usernames: list[str] = Field(default_factory=list)


class RenameChatRequest(BaseModel):
    title: str = Field(min_length=1, max_length=48)


class TicketRequest(BaseModel):
    ticket_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    repo_ids: list[str] = Field(default_factory=list)
    logs: str = ""
    image_urls: list[str] = Field(default_factory=list)


class IngressEventRequest(BaseModel):
    """外部系统推送事件（统一入口）。"""

    source: str = Field(min_length=1, description="来源系统标识，如 jira / monitor")
    project_id: str = Field(
        min_length=1,
        description="DeepTicket 项目 ID，用于加载关联代码仓库与 MCP",
    )
    external_id: str = Field(min_length=1, description="外部系统侧唯一 ID")
    question: str = Field(min_length=1, description="交给 Agent 分析的问题描述")
    image_urls: list[str] = Field(
        default_factory=list,
        description="可选；工单附带的图片 URL（http/https）",
    )
    extensions: dict = Field(
        default_factory=dict,
        description="调用方扩展字段；出站原样回传",
    )


class IngressJobResponse(BaseModel):
    job_id: str
    status: str
    source: str
    project_id: str
    external_id: str
    reply: str = ""
    extensions: dict = Field(default_factory=dict)
    error: str | None = None
    outbound_method: str = ""
    outbound_ok: bool = False
    outbound_detail: str = ""


class RouteInfoResponse(BaseModel):
    type: str
    description: str
    outbound_method: str


class UserResponse(BaseModel):
    uid: str
    username: str
    is_admin: bool = False


class OkResponse(BaseModel):
    ok: bool = True


class CancelAgentRequest(BaseModel):
    conversation_id: str | None = Field(default=None, min_length=1)
    chat_id: str | None = Field(default=None, min_length=1)
