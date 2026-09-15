# DeepTicket 项目链路与启动指南

## 项目定位

DeepTicket 是部署在团队自己环境里的 AI 工单排障与 Agent 编排平台。它把内部工单/告警事件送进 Agent，将项目源码、日志 Skill、配置中心 MCP 和其他内部工具接到同一次分析中，再把带证据的结论回写原工单系统。

## 核心链路

### 1. 用户对话链路（Web UI）

```
浏览器 → DeepTicket Web (8600) → ChatOrchestrator → OpenHandsEngine
         → OpenHands Agent Server (8100) → LLM API
         → 流式回复 / 活动日志 / 置信度 → 存储（Redis 或本地文件）
```

- 用户在 Web 工作台发起对话，`ChatOrchestrator.run_chat_stream` 编排。
- 引擎对接 OpenHands Agent Server（HTTP + WebSocket），流式获取回复。
- 结论与过程写回存储：会话历史、调查 Run、Token 用量、活动日志等。

### 2. Ingress 工单链路（外部系统接入）

```
外部工单/告警 → POST /api/ingress/events（Ingress API Key 鉴权）
  → classify_ingress_event（按 source/关键词匹配路由）
  → IngressAdapter.to_ticket（转为内部 TicketInput）
  → IngressJobQueue（异步队列）
  → ChatOrchestrator.run_ticket_stream → OpenHandsEngine → LLM
  → OutboundHandler（store_only 或 webhook 回调外部系统）
  → IngressJob 结果持久化（Redis / 本地）
```

- 路由按 `deepticket.yaml` 中 `ingress.routes` 顺序匹配，未命中走 default。
- `store_only`：结果仅写入存储，通过 `GET /api/ingress/jobs/{id}` 查询。
- `webhook`：分析完成后回调外部工单系统。

### 3. 知识层

- 启动或手动同步时，从 Git 拉取只读代码到 `workspace/knowledge/`。
- 再链接到 `workspace/project/` 供 Agent 检索（多项目隔离）。
- Skill（如 log-query、config-query）发布到 `workspace/project/.openhands/skills/`。

### 4. 工具治理链路

- MCP 工具调用经过 `ToolGovernanceGate`。
- 策略决策支持 `allow` / `deny` / `require_approval`。
- `deny` → 硬拦截，Run 状态为 policy_denied。
- `require_approval` → 创建审批单，Run 状态为 waiting_approval。

## 存储层

| 后端 | 配置 | 说明 |
|------|------|------|
| Redis（默认） | `storage.backend: redis` | 推荐；支持业务数据 + Ingress 任务 + 会话历史 |
| local | `storage.backend: local` | 写入 `./data` 目录（JSON 文件） |

## 项目启动

### 方式一：Docker（推荐，最简）

```bash
cp .env.docker.example .env
# 可选：编辑 .env 填写 LLM_API_KEY=sk-...
docker compose up -d --build
```

浏览器打开 http://127.0.0.1:8600 ，默认账户 `admin` / `admin`。

### 方式二：本地 venv（开发调试）

```bash
bash scripts/setup.sh
# 可选：编辑 deepticket.yaml 填写 llm.api_key
bash scripts/start_all.sh
```

`start_all.sh` 会自动：
1. 如无 `.venv` 则执行 `setup.sh`
2. 从 `deepticket.yaml` 导出环境变量
3. 如 `STORAGE_BACKEND=redis` 且非远端则通过 Docker 启动 Redis
4. 启动 OpenHands Agent Server（8100）
5. 等待 Agent Server 健康检查通过
6. 启动 DeepTicket Web（8600）

## 常用命令

```bash
docker compose logs -f deepticket    # 查看日志
docker compose down                  # 停止 Docker 服务
bash scripts/verify.sh               # 本地自检
bash scripts/run_local_tests.sh      # 本地测试
```

## 关键配置

配置文件为 `deepticket.yaml`（从 `deepticket.example.yaml` 复制），主要模块：

| 模块 | 说明 |
|------|------|
| `llm` | OpenAI 兼容模型、API Key、Base URL |
| `web` | Web 监听地址与端口（默认 8600） |
| `auth` | 登录策略、bootstrap 用户 |
| `storage` | Redis / local 后端选择 |
| `knowledge` | Git 仓库、workspace 目录 |
| `extensions` | Skill 目录、agents_md |
| `ingress` | API Key、路由规则、outbound 配置 |
| `mcp` | MCP servers（默认关闭） |
| `tool_governance` | 工具策略（allow / deny / require_approval） |

LLM 未配置时服务仍可启动（Agent 不可用），可在 Web「LLM 配置」页补填。
