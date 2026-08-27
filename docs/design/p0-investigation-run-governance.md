# P0 设计方案：Investigation Run · Event Stream · Tool Governance

> **版本：** v0.4.0 目标  
> **原则：** OpenHands 负责「想和做」；DeepTicket 负责「记录、约束、治理」。  
> **非目标：** 替换 OpenHands、强制 Evidence→Hypothesis 工作流、外部审批系统。

---

## 1. 现状与缺口

| 能力 | 现状（v0.3.3） | 缺口 |
|------|----------------|------|
| 任务生命周期 | `ChatRunManager` 内存 + Redis `agent_run_status` | 无持久 Run 实体；重启丢进程内状态 |
| Agent 过程 | SSE `StreamChunk` 实时推送；OH workspace events | DeepTicket 无结构化 Event 表 |
| Tool 执行 | OH 直接调 MCP；`NeverConfirm` 为主 | 无 MCP/Tool 级策略拦截 |
| Ingress | `IngressRunner` 独立队列 | 与 chat run 状态模型不统一 |
| OH 状态 | 轮询 `execution_status` | 仅 Runtime 信号，非 DeepTicket Run |

OpenHands 自有 `ConversationExecutionStatus`（`idle/running/waiting_for_confirmation/finished/error/stuck`），**不能**当作 DeepTicket InvestigationRun，只能映射为 Runtime 子状态。

---

## 2. 目标架构

```text
                    DeepTicket
                         │
     ┌───────────────────┼───────────────────┐
     ▼                   ▼                   ▼
InvestigationRun    PolicyEngine         RunEventStore
 (状态机, Redis)    (YAML 三级策略)      (Timeline, Redis)
     │                   │                   │
     │                   ▼                   │
     │            ToolGovernanceHook         │
     │            ALLOW/DENY/APPROVAL        │
     │                   │                   │
     └───────────────────┼───────────────────┘
                         ▼
              AgentRuntimeAdapter
              (OpenHandsEngine)
                         ▼
                   OpenHands + MCP
```

---

## 3. InvestigationRun

### 3.1 实体

```python
@dataclass
class InvestigationRun:
    run_id: str              # uuid hex
    project_id: str
    uid: str                 # 发起人
    source: str              # chat | ingress | ticket
    chat_id: str | None
    ingress_job_id: str | None
    ticket_id: str | None

    status: RunStatus
    oh_conversation_id: str | None   # 当前 Runtime 挂载点，可重建

    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    error_message: str | None

    # 统计（冗余，便于列表 UI）
    tool_call_count: int
    event_count: int
```

### 3.2 状态机（v1）

```text
CREATED → QUEUED → RUNNING ⇄ WAITING_APPROVAL → COMPLETED
                      │              │
                      ├→ FAILED      └→ (审批拒绝) → FAILED / CANCELLED
                      └→ CANCELLED
```

| 状态 | 含义 |
|------|------|
| `CREATED` | Run 记录已写入，尚未调度 |
| `QUEUED` | 等待 worker（Ingress 队列或 chat 并发槽） |
| `RUNNING` | Agent Runtime 活跃；映射 OH `running` |
| `WAITING_APPROVAL` | Tool 策略 `REQUIRE_APPROVAL`；Run 暂停，**不**挂 coroutine |
| `COMPLETED` | 正常结束；OH `finished` 且 DeepTicket 收尾完成 |
| `FAILED` | 不可恢复错误；OH `error/stuck` 或治理 DENY |
| `CANCELLED` | 用户取消 |

**转换规则（节选）：**

- `CREATED → QUEUED`：`RunExecutor.enqueue(run_id)`
- `QUEUED → RUNNING`：worker 开始调 `OpenHandsEngine.stream`
- `RUNNING → WAITING_APPROVAL`：Governance 返回 `REQUIRE_APPROVAL` 且已持久 `ApprovalRequest`（P1 实现审批 UI；P0 可先 `FAILED` + 明确错误）
- `RUNNING → COMPLETED`：engine 流结束且无未决审批
- `RUNNING → FAILED`：HTTP/Runtime 异常、Policy DENY
- 任意非终态 → `CANCELLED`：`POST /api/runs/{id}/cancel`

终态不可再转；新用户消息 / 新 Ingress 事件 → **新 Run**（同 chat 可有多 Run，chat 消息关联 `run_id`）。

### 3.3 Redis 存储

沿用现有 `StorageBackend` 模式：

| 命名空间 | Key | 结构 |
|----------|-----|------|
| `inv_runs` | `{project}:{uid}:zset` | run_id → score(updated_at) |
| `inv_run` | `{project}:{run_id}` | Hash 元数据 |
| `inv_run_events` | `{project}:{run_id}:zset` | event_id → seq |
| `inv_run_event` | `{project}:{event_id}` | Hash event body |

索引：`chat_id → run_ids`（ZSET）、`ingress_job_id → run_id`（Hash）。

**与 chat thread 关系：**

- `chat_history` 保留 UI 消息；每条 assistant 消息增加 `run_id` 字段。
- 逐步废弃 thread 级 `agent_run_status`，改查「该 chat 最新非终态 Run」。

---

## 4. RunEvent（Agent Trace）

### 4.1 事件模型

```python
@dataclass
class RunEvent:
    event_id: str
    run_id: str
    seq: int                    # Run 内单调递增
    type: RunEventType
    timestamp: str              # ISO UTC
    payload: dict[str, Any]     # 类型相关字段
```

### 4.2 事件类型（v1）

| type | 来源 | payload 示例 |
|------|------|----------------|
| `RUN_CREATED` | DeepTicket | source, chat_id |
| `RUN_STATUS_CHANGED` | DeepTicket | from, to |
| `AGENT_MESSAGE` | OH MessageEvent | role, text_preview |
| `TOOL_CALL` | OH ActionEvent | tool, mcp, arguments_preview |
| `TOOL_RESULT` | OH ObservationEvent | tool, status, summary |
| `POLICY_DECISION` | Governance | tool, decision, reason |
| `ERROR` | OH / DT | code, message |
| `RUN_COMPLETED` | DeepTicket | status, token_usage |

### 4.3 采集路径

在 `OpenHandsEngine._push_event` / WebSocket 订阅处：

1. 解析 OH event → `RunEvent`（已有 `format_agent_activity` 可复用分类逻辑）。
2. `RunEventStore.append(run_id, event)` — 同步写 Redis（append-only）。
3. 继续 `out_queue.put(StreamChunk(...))` — **不破坏现有 SSE**。

OH `events/search` 仅作补全/对账；主路径是 WS 实时映射。

### 4.4 API（v1）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/runs/{run_id}` | Run 元数据 + 统计 |
| GET | `/api/runs/{run_id}/events?after_seq=&limit=` | Timeline 分页 |
| GET | `/api/chats/{chat_id}/runs` | 某会话的 Run 列表 |

工作台 v1：Thinking 面板增加「Run Timeline」Tab，读 events API；SSE 仍作实时增量。

---

## 5. Tool Governance

### 5.1 拦截点

OpenHands 1.x 通过 MCP 执行 tool；DeepTicket **第一版**在以下位置拦截：

**方案 A（推荐 P0）：OH SecurityAnalyzer / Hook 扩展**

- 注册 DeepTicket `GovernanceSecurityAnalyzer`（或 SDK Hook），在 tool execute 前调用 `PolicyEngine.evaluate(...)`。
- 返回 allow → 继续；deny → 抛错并写 `POLICY_DECISION` + `ERROR` event；require_approval → P0 写 event + Run→FAILED（P1 改 WAITING_APPROVAL）。

**方案 B（备选）：Engine 层包装 MCP config**

- 若 OH 不支持同步 hook，在 `agent_settings.mcp_config` 前加 proxy MCP（复杂度高，P0 不采用）。

### 5.2 PolicyEngine

配置挂载在 `deepticket.yaml`（或 per-project override）：

```yaml
tool_governance:
  global:
    default: allow
  mcp:
    kubernetes:
      default: allow
      unknown_tool_mode: strict   # open | audit | strict  (P1)
  tools:
    "kubernetes.exec":
      decision: require_approval
    "kubernetes.delete_pod":
      decision: require_approval
    "kubernetes.delete_namespace":
      decision: deny
```

**优先级：** `tools.*` > `mcp.{name}.*` > `global.default`

**evaluate 输入：**

```python
PolicyContext(
    actor_uid, actor_roles,   # P1 细粒度
    project_id,
    environment,              # 来自 project 或 yaml
    mcp_server,
    tool_name,
    arguments,                # P1 解析 SQL 等
)
→ PolicyDecision(ALLOW | DENY | REQUIRE_APPROVAL, reason)
```

### 5.3 MCP Tool Registry

```python
class McpToolRegistry:
    async def refresh(server_id: str) -> list[ToolDescriptor]
    async def get_tool(server_id, tool_name) -> ToolDescriptor | None
```

- 项目启用 MCP 时 / Admin 保存配置时：调用 MCP `tools/list`，缓存到 Redis `mcp_tools:{project}:{server}` + TTL。
- **策略评估不依赖启动时已知全集**；未知 tool 在 call 时按 `unknown_tool_mode` 处理（P1 STRICT）。

---

## 6. 与 OpenHands Runtime 的映射

| OH `execution_status` | DeepTicket Run（在 RUNNING 子状态下） |
|------------------------|----------------------------------------|
| `idle` | QUEUED 或 RUNNING（刚 POST message 前） |
| `running` | RUNNING |
| `waiting_for_confirmation` | RUNNING 或 WAITING_APPROVAL（视是否 DT 审批） |
| `finished` | → COMPLETED（engine 收尾后） |
| `error` / `stuck` | → FAILED |
| `paused` | RUNNING + 子标志（可选） |

OH conversation 重建（续聊 sync）时：**同一 Run** 更新 `oh_conversation_id`，写 `RUN_STATUS_CHANGED` event，Run 状态保持 `RUNNING`。

---

## 7. ChatRunManager 迁移

### 7.1 阶段计划

| 阶段 | 行为 |
|------|------|
| **Phase 1** | 新增 `InvestigationRunStore` + `RunExecutor`；`ChatRunManager._execute` 开头创建 Run，结束更新终态 |
| **Phase 2** | SSE 订阅改为 `run_id`；`/api/chats/.../status` 读最新 Run 状态 |
| **Phase 3** | 删除内存 `_ChatRun` 的 status 职责，仅保留 subscriber fan-out（或改为 Run 级订阅） |
| **Phase 4** | `IngressRunner` 共用 `RunExecutor` |

### 7.2 并发

现规则：同 chat 仅一个进行中的 Agent 任务 → 改为同 chat 仅一个非终态 Run。

---

## 8. 目录与模块（建议）

```text
deepticket/
  investigation/
    models.py           # InvestigationRun, RunStatus, RunEvent
    store.py            # InvestigationRunStore, RunEventStore
    executor.py         # RunExecutor（调度、状态转换）
    policy/
      engine.py         # PolicyEngine
      schema.py         # YAML 配置模型
    governance/
      hook.py           # OH SecurityAnalyzer / hook 注册
    registry/
      mcp_tools.py      # McpToolRegistry
  api/routers/runs.py   # GET run, events, cancel
```

`OpenHandsEngine` 注入 `run_id`，WS 回调写 Event。

---

## 9. 实施顺序（P0 里程碑）

| 里程碑 | 交付 | 预估 |
|--------|------|------|
| **M1** | `InvestigationRun` 模型 + Store + 状态机单元测试；chat 路径 CREATED→COMPLETED | 小 |
| **M2** | WS→RunEvent 写入 + GET events API；SSE 不变 | 中 |
| **M3** | PolicyEngine YAML + DENY/ALLOW；Governance hook 接入 OH | 中 |
| **M4** | McpToolRegistry refresh + 未知 tool 日志 | 小 |
| **M5** | chat status / cancel 迁到 Run；废弃 `agent_run_status` | 小 |
| **M6** | Ingress 共用 Run（可选放 v0.4.1） | 中 |

**P0 验收：**

1. 发一条 chat → Redis 有 Run + Event 序列；刷新后可 GET timeline。
2. 配置 `kubernetes.delete_namespace: deny` → tool 不执行，Run 记录 `POLICY_DECISION`。
3. 服务重启 → 进行中 Run 标记 FAILED 或 recoverable（v1 可简化为 FAILED + 用户重试）。

---

## 10. 测试策略

- 单元：`RunStatus` 转换表；`PolicyEngine` 优先级；event 序列单调。
- 集成：mock OH WS 事件 → events API 断言。
- E2E：`scripts/verify_continue_chat.py` 扩展断言 `run_id` + events 条数。
- Governance：fixture YAML + mock tool call → DENY 不触发 OH execute。

---

## 11. 后续（P1，不在 P0 范围）

- `ApprovalRequest` 表 + Web Approve/Reject + `WAITING_APPROVAL` resume
- `unknown_tool_mode: strict`
- Role × Environment 维度的 Policy
- 工作台 Run 头 + Timeline UI 正式版

---

## 12. 参考

- 现有代码：`chat_runs.py`、`openhands_engine.py`、`chat_history.py`、`ingress_runner.py`
- OpenHands：`ConversationExecutionStatus`（`openhands.sdk.conversation.state`）
- 本地待办：`docs/LOCAL-BACKLOG.md` §十一
