# 核心链路逐行代码走读

本文档将项目最核心的两条链路的代码逐行标注，帮助你理解每一行的作用。

---

## 链路一：用户对话（Chat）

### 调用链

```
POST /api/chats/{id}/stream
  → chats.py (路由)
  → ChatOrchestrator.run_chat_stream()   ← 本节重点
  → OpenHandsEngine.stream()
  → Agent Server (8100) → LLM API
```

### `deepticket/service.py` — DeepTicketService.__init__

```python
class DeepTicketService:
    """五层编排：输入 → 知识/存储 → 引擎 → 输出（依赖注入的根节点）。"""

    def __init__(self, config, *, llm_model, llm_api_key, llm_base_url, llm_label):
        # 保存配置对象（Pydantic AppConfig，包含所有 yaml 配置）
        self.config = config
        self.llm_label = llm_label          # LLM 显示名（Web UI 用）

        # ── 存储层 ──
        # 根据 config.storage.backend 创建 Redis 或本地 JSON 存储后端
        self.storage = create_storage(config.storage)
        self.users = UserStore(self.storage)             # 用户账号读写
        self.chat_history = ChatHistoryStore(self.storage)  # 对话历史读写

        # ── Investigation Run 子系统 ──
        self.investigation_runs = InvestigationRunStore(self.storage)  # 调查任务状态机
        self.run_events = RunEventStore(self.storage, run_store=...)   # Run 事件流
        self.approval_requests = ApprovalRequestStore(self.storage)    # 审批单存储
        self.mcp_tool_registry = McpToolRegistry(self.storage)         # MCP 工具注册表
        self.policy_engine = PolicyEngine(config.tool_governance)      # 策略评估引擎
        self.governance_gate = ToolGovernanceGate(                     # 治理网关
            self.policy_engine, self.run_events,
            approval_store=self.approval_requests,
            tool_registry=self.mcp_tool_registry,
        )
        self.governance_context_store = GovernanceContextStore(self.storage)
        self.token_usage = TokenUsageStore(self.storage)  # Token 用量统计

        # ── 项目管理 ──
        self.projects = ProjectRegistry(self.storage, config, ...)

        # ── 知识层 ──
        self.knowledge = KnowledgeManager(config.knowledge)  # Git 同步
        self.skills = SkillManager(...)                      # Skill 发布到 workspace

        # ── 引擎层 ──
        self.engine = OpenHandsEngine(config.engine, llm_model=..., ...)
        # 注入治理组件到引擎（引擎收到 MCP 工具调用事件时回调 gate 评估）
        self.engine.run_events = self.run_events
        self.engine.governance_gate = self.governance_gate

        # ── Ingress + Chat 编排 ──
        self.routing = RoutingConfig(routes=list(config.ingress.routes))
        self.ingress = IngressRunner(self)      # 外部事件入队与执行
        self.chat = ChatOrchestrator(self)      # 聊天/工单流编排
        self.chat_runs = ChatRunManager(self)   # 聊天 Run 管理（订阅/取消）
```

### `deepticket/chat_orchestrator.py` — run_chat_stream()

```python
async def run_chat_stream(self, payload, *, project, uid=None, chat_id=None):
    # 1. LLM 未配置则直接抛异常，阻止进入 Agent
    self._service.require_llm_configured()

    # 2. 没有 uid/chat_id（新会话）：直接创建 AgentInput 并流式执行
    if not uid or not chat_id:
        agent_input = InputAdapter.from_chat(payload)      # ChatInput → AgentInput
        agent_input.image_urls = self.resolve_agent_image_urls(...)  # 内嵌本地上传图片
        self.apply_project_runtime(agent_input, project)   # 注入 workspace/MCP/Skill
        async for chunk in self._run_stream(agent_input):  # 调引擎流式输出
            yield chunk
        return

    # 3. 有 uid/chat_id（已有会话）：走完整流程
    agent_input = InputAdapter.from_chat(payload)
    stored_image_urls = list(agent_input.image_urls)       # 保存原始图片 URL 列表
    agent_input.image_urls = self.resolve_agent_image_urls(stored_image_urls)
    self.apply_project_runtime(agent_input, project)       # 注入项目运行时配置

    # 4. 从存储中读取会话摘要（含 agent_conversation_id）
    thread = self._service.chat_history.get_thread_summary(project.project_id, uid, chat_id)
    if thread is None:
        raise RuntimeError(f"聊天不存在: {chat_id}")

    # 5. 复用 OpenHands Conversation ID（实现多轮对话）
    if thread.get("agent_conversation_id") and not agent_input.conversation_id:
        agent_input.conversation_id = thread["agent_conversation_id"]

    # 6. 将本轮用户消息写入存储（先写再执行）
    self._service.chat_history.append_message(
        project.project_id, uid, chat_id,
        role="user", content=payload.message.strip(),
        image_urls=stored_image_urls or None,
    )

    # 7. 读取完整线程消息，构建 OpenHands 回放历史
    full_thread = self._service.chat_history.get_thread(project.project_id, uid, chat_id)
    agent_input.history_messages = self._history_from_thread(
        full_thread, current_user_message=payload.message.strip(),
    )

    # 8. 通过 ChatRunManager 启动 Run（内部创建/复用 OH Conversation）
    run = await self._service.chat_runs.start(
        project=project, uid=uid, chat_id=chat_id,
        payload=payload, agent_input=agent_input,
    )

    # 9. 订阅 Run 的流式输出，逐 chunk 转发给调用方
    try:
        async for chunk in self._service.chat_runs.subscribe(run):
            yield chunk
    except asyncio.CancelledError:
        return   # 客户端断开则静默退出
```

### `deepticket/chat_orchestrator.py` — run_ticket_stream()（工单链路）

```python
async def run_ticket_stream(self, payload, *, project, uid=None, ingress_job_id=None):
    self._service.require_llm_configured()
    agent_input = InputAdapter.from_ticket(payload)   # TicketInput → AgentInput
    self.apply_project_runtime(agent_input, project)

    run_uid = uid or resolve_system_uid(self._service)  # Ingress 无用户时用系统 UID
    source = RunSource.INGRESS if ingress_job_id else RunSource.TICKET

    # 直接创建 InvestigationRun（工单不走 ChatRunManager）
    investigation_run = begin_investigation_run(
        self._service.investigation_runs, self._service.run_events,
        project_id=project.project_id, uid=run_uid,
        source=source, agent_input=agent_input,
        ingress_job_id=ingress_job_id, ticket_id=payload.ticket_id,
    )

    # 将工单元数据写入存储（ticket_id → run_id 映射）
    self._service.storage.set_json("tickets", payload.ticket_id, {...})

    assistant_parts = []    # 收集流式回复文本片段
    activity_log = []       # 收集 Agent 活动日志
    terminal_status = RunStatus.COMPLETED  # 默认终态

    try:
        async for chunk in self._run_stream(agent_input):
            if chunk.activity:  # Agent 活动日志（工具调用等）
                activity_log.append({"text": chunk.activity, "kind": ...})
            if chunk.delta:     # 流式回复文本
                assistant_parts.append(chunk.delta)
            if chunk.policy_denied:  # 策略拒绝
                terminal_error = chunk.policy_message
            yield chunk         # 转发给调用方

        # 流结束后计算置信度并作为最后一个 chunk yield
        yield StreamChunk(confidence=compute_confidence(
            activities=activity_log, reply="".join(assistant_parts), ok=True,
        ))
    except PolicyApprovalRequiredError:
        terminal_status = RunStatus.WAITING_APPROVAL  # 需要人工审批
    except Exception:
        terminal_status = RunStatus.FAILED
        raise
    finally:
        # 无论成功失败，都将 InvestigationRun 推到终态
        self._service.investigation_runs.transition(
            project.project_id, investigation_run.run_id,
            terminal_status, error_message=terminal_error,
            event_store=self._service.run_events,
        )
```

---

## 链路二：Ingress 工单（外部事件 → 分析 → 回调）

### 调用链

```
POST /api/ingress/events
  → ingress.py (路由 + API Key 鉴权)
  → IngressRunner.submit()       ← 入队
  → worker → IngressRunner.run_event()  ← 执行
  → ChatOrchestrator.run_ticket_stream() → Agent 分析
  → OutboundHandler.deliver()    ← 回调
```

### `deepticket/ingress_runner.py` — submit()

```python
async def submit(self, event: IngressEvent) -> IngressJobResult:
    self._service.require_llm_configured()          # LLM 必须已配置
    self._service.projects.require(event.project_id)  # 项目必须存在
    route = classify_ingress_event(event, self._service.routing)  # 匹配路由规则
    extensions = copy.deepcopy(event.extensions)     # 快照扩展字段
    job_id = uuid.uuid4().hex                        # 生成唯一任务 ID

    # 创建初始状态为 queued 的任务文档并持久化
    queued_doc = {
        "job_id": job_id, "status": "queued", ...
        "outbound_method": route.outbound.method,   # store_only 或 webhook
    }
    self._persist_job(job_id, queued_doc)            # 写入存储 + 索引

    # 放入异步队列，worker 会调用 run_event()
    await self._queue.enqueue(IngressJobItem(job_id=job_id, event=event))
    return IngressJobResult(**{k: v for k, v in queued_doc.items() if ...})
```

### `deepticket/ingress_runner.py` — run_event()

```python
async def run_event(self, event, *, job_id=None):
    route = classify_ingress_event(event, self._service.routing)
    ticket = IngressAdapter.to_ticket(event, route)  # IngressEvent → TicketInput

    # 更新状态为 running
    existing.update({"status": "running", ...})
    self._persist_job(job_id, existing)

    reply = ""
    error = None
    status = "finished"
    try:
        project = self._service.projects.require(event.project_id)
        # 调用 ChatOrchestrator 工单链路，收集完整回复文本
        reply, _, _ = await collect_stream_text(
            self._service.chat.run_ticket_stream(ticket, project=project, ingress_job_id=job_id)
        )
    except Exception as exc:
        status = "failed"
        error = str(exc)

    # 构建出站负载
    outbound_payload = OutboundPayload(
        source=event.source, project_id=..., external_id=...,
        status=status, reply=reply, extensions=..., error=error,
    )
    # 根据路由配置选择出站处理器（store_only 或 webhook）并投递
    handler = get_outbound_handler(route.outbound.method)
    outbound_result = await handler.deliver(outbound_payload, route.outbound)

    # 持久化最终结果
    result = IngressJobResult(job_id=..., status=..., reply=..., ...)
    self._persist_job(job_id, {**asdict(result), "updated_at": utc_now_iso()})
    return result
```

### `deepticket/layers/output/outbound/registry.py` — WebhookOutbound.deliver()

```python
class WebhookOutbound:
    async def deliver(self, payload, config: OutboundConfig) -> OutboundResult:
        # 1. 解析回调 URL（url 字段优先，否则读 url_env 环境变量）
        url = resolve_outbound_url(config.url, config.url_env)
        if not url:
            return OutboundResult(method="webhook", ok=False, detail="URL 未配置")

        # 2. 构建请求头（可从环境变量注入额外 JSON 头）
        headers = {"Content-Type": "application/json"}

        # 3. 构建回调 body
        body = {
            "source": payload.source,
            "project_id": payload.project_id,
            "external_id": payload.external_id,
            "status": payload.status,      # finished 或 failed
            "reply": payload.reply,        # Agent 分析结果全文
            "extensions": payload.extensions,
            "error": payload.error,
        }

        # 4. POST 回调外部系统
        async with httpx.AsyncClient(timeout=config.timeout_seconds, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=body)

        # 5. 处理响应
        if resp.status_code >= 400:
            return OutboundResult(method="webhook", ok=False, detail=resp.text[:500])
        return OutboundResult(method="webhook", ok=True, detail="已回调外部系统")
```

---

## 链路三：知识层（Git 同步）

### `deepticket/layers/knowledge/manager.py` — KnowledgeManager.sync_all()

```python
class KnowledgeManager:
    """Git 只读 clone → cache → 链接到 workspace 供 Agent 检索。"""

    def __init__(self, config: KnowledgeConfig):
        self.config = config
        self.cache_dir = Path(config.git_cache_dir)     # workspace/knowledge/
        self.workspace_dir = Path(config.workspace_dir)  # workspace/project/
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def sync_all(self) -> list[GitSyncResult]:
        results = []
        for repo in self.config.repos:
            results.append(self._sync_one(repo))
        return results

    def _sync_one(self, repo: GitRepoConfig) -> GitSyncResult:
        # 1. 构建带 token 的 Git URL（GitHub/GitLab 自动适配认证格式）
        auth_url = build_authenticated_git_url(repo.url, repo.key, repo.url_template)

        # 2. clone 到 cache 目录（workspace/knowledge/{repo_id}/）
        cache_path = self.cache_dir / repo.id
        if cache_path.exists():
            subprocess.run(["git", "pull"], cwd=cache_path)  # 已有则 pull
        else:
            subprocess.run(["git", "clone", "--branch", repo.branch, auth_url, str(cache_path)])

        # 3. 将 cache 目录设为只读（防止 Agent 修改代码）
        self._make_tree_readonly(cache_path)

        # 4. 链接/复制到 workspace/project/{workspace_subdir}/ 供 Agent 检索
        target = self.workspace_dir / repo.workspace_subdir
        if target.exists():
            shutil.rmtree(target)  # 先删除旧链接
        shutil.copytree(str(cache_path), str(target), symlinks=True)

        return GitSyncResult(repo_id=repo.id, cache_path=..., workspace_path=..., ...)
```

---

## 链路四：引擎层（OpenHands 对接）

### `deepticket/layers/engine/openhands_engine.py` — OpenHandsEngine

```python
class OpenHandsEngine:
    """对接 OpenHands Agent Server（HTTP + WebSocket）。"""

    def __init__(self, config, *, llm_model, llm_api_key, llm_base_url, workspace_dir):
        self.config = config
        self.llm_model = llm_model           # 如 anthropic/z-ai/glm-5.3-flash
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url     # 如 https://copilot.huya.info/api/anthropic
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self._agent_timeout_seconds = config.agent_timeout_seconds  # 默认 600s
        self._cancel_events = {}             # 取消信号（conversation_id → Event）
        self.server = f"http://{config.agent_server_host}:{config.agent_server_port}"
        self.gateway_model = f"openhands_{config.llm_profile}"  # 内部 profile 名

    # ── HTTP 客户端 ──
    def _client(self, timeout=60.0):
        return httpx.AsyncClient(timeout=timeout, trust_env=False)

    def _headers(self, *, stream=False):
        headers = {"Content-Type": "application/json"}
        if self.config.session_api_key:
            headers["X-Session-API-Key"] = self.config.session_api_key  # Agent Server 鉴权
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _ws_url(self, conversation_id: str) -> str:
        # WebSocket URL 用于接收 Agent 实时事件流
        url = f"ws://{host}:{port}/sockets/events/{conversation_id}"
        if self.config.session_api_key:
            url += f"?session_api_key={self.config.session_api_key}"
        return url

    # ── LLM Profile 注册 ──
    async def _register_profile(self):
        """将 LLM 配置注册到 Agent Server（POST /api/profiles/{name}）。"""
        body = {
            "llm": {"model": self.llm_model, "api_key": ..., "base_url": ..., "stream": True},
            "include_secrets": True,
        }
        resp = await client.post(f"{self.server}/api/profiles/{self.config.llm_profile}", ...)

    # ── MCP 配置同步 ──
    async def sync_mcp_config(self, servers: dict):
        """将 MCP servers 配置同步到 Agent Server（PATCH /api/settings）。"""
        body = {"agent_settings_diff": {"mcp_config": servers}}
        resp = await client.patch(f"{self.server}/api/settings", ...)
```

### 核心方法 stream()（简化伪码）

```python
async def stream(self, agent_input: AgentInput):
    # 1. 创建或复用 OpenHands Conversation
    conversation_id = agent_input.conversation_id or await self._create_conversation(agent_input)

    # 2. 发送用户消息（POST /api/conversations/{id}/start）
    await self._start_task(conversation_id, agent_input)

    # 3. 连接 WebSocket 监听事件流
    async with websockets.connect(self._ws_url(conversation_id)) as ws:
        async for raw_event in ws:
            event = json.loads(raw_event)
            # 4. 治理拦截：如果是 MCP 工具调用，先过 ToolGovernanceGate
            if mcp_tool_call := extract_mcp_tool_call(event):
                result = self.governance_gate.evaluate_mcp_tool(...)
                if result.hard_block:
                    raise PolicyDeniedError / PolicyApprovalRequiredError
            # 5. 映射为 StreamChunk（delta / activity / confidence / policy_denied）
            chunk = map_openhands_event(event)
            yield chunk
            # 6. 收到终态事件则退出
            if event.get("status") in _TERMINAL_STATUSES:
                break
```

---

## 链路五：工具治理

### `deepticket/investigation/governance/gate.py` — ToolGovernanceGate

```python
class ToolGovernanceGate:
    """MCP 工具治理网关：策略评估 → 审计事件 → 审批单创建。"""

    def evaluate_context(self, ctx: ToolInvocationContext) -> ToolGovernanceResult:
        # 1. 策略引擎评估（基于 tool_governance.yaml 配置）
        evaluation = self._policy.evaluate(ctx)

        # 2. 记录审计事件
        if self._events and ctx.run_id:
            self._events.append(ctx.project_id, ctx.run_id, RunEventType.TOOL_INVOKED, {...})

        # 3. 根据决策返回结果
        if evaluation.decision is PolicyDecision.ALLOW:
            return ToolGovernanceResult(evaluation=evaluation, blocked=False)

        if evaluation.decision is PolicyDecision.DENY:
            # 硬拦截：记录 policy_denied 事件
            self._record_block_event(ctx.project_id, ctx.run_id, message, code="policy_denied")
            return ToolGovernanceResult(evaluation=..., blocked=True, hard_block=True, ...)

        # REQUIRE_APPROVAL：创建审批单，Run 状态变为 waiting_approval
        request = self._approvals.create(project_id=..., run_id=..., tool_name=..., ...)
        self._record_block_event(ctx.project_id, ctx.run_id, message, code="approval_required")
        return ToolGovernanceResult(evaluation=..., blocked=True, waiting_approval=True, ...)
```

---

## 学习建议

1. 先读 `service.py` 的 `__init__`，理解组件怎么组装
2. 跟着 `run_chat_stream` 走一遍完整调用链
3. 对着本文档和源码，用 IDE 的 "Go to Definition" 逐层跳转
4. Ingress 链路相对简单，适合第二个学习
5. 引擎层 `openhands_engine.py` 是最大的文件（~1200 行），重点看 `stream()` 和 `_push_event()`
