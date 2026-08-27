import { renderMarkdown } from "/static/markdown.js?v=16";
import { App, TOKEN_KEY, PROJECT_KEY, RECORD_MODE_KEY, hideAdminPanels, updateAdminNavActive, formatToken } from "./app-shared.js";
import { openDashboard, wireAdminToken } from "./admin-token.js";
import { openLlmAdmin, wireAdminLlm } from "./admin-llm.js";
import { openProjectAdmin, wireAdminProjects } from "./admin-projects.js";

const ASSET_VERSION = "14";
const MASCOT_ICON = "/static/mascot-icon.png";

const ACTIVITY_ICONS = {
  log: "📋",
  config: "⚙️",
  code: "📁",
  skill: "🧩",
  search: "🔍",
  terminal: "⌨️",
  think: "💡",
  evidence: "🔎",
  handoff: "✓",
  error: "⚠️",
  system: "◆",
  default: "•",
};

const CONFIDENCE_ANALYSIS_KINDS = new Set([
  "log",
  "config",
  "code",
  "skill",
  "search",
  "terminal",
  "evidence",
  "error",
]);

const ICONS = {
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
};

/* DOM 引用 */
const $ = (id) => document.getElementById(id);
const userLabel = $("userLabel");
const userAvatar = $("userAvatar");
const menuUserName = $("menuUserName");
const chatListEl = $("chatList");
const chatTitleEl = $("chatTitle");
const messagesEl = $("messages");
const messagesInner = messagesEl.querySelector(".messages-inner");
const emptyStateEl = $("emptyState");
const promptEl = $("prompt");
const chatForm = $("chatForm");
const attachmentStripEl = $("attachmentStrip");
const imageFileInputEl = $("imageFileInput");
const attachBtnEl = $("attachBtn");
const sendBtn = $("sendBtn");
const stopBtn = $("stopBtn");
const statusEl = $("status");
const statusPill = $("statusPill");
const runStatusPill = $("runStatusPill");
const runStatusText = $("runStatusText");
const modelLabelEl = $("modelLabel");
const knowledgeLabelEl = $("knowledgeLabel");
const storageLabelEl = $("storageLabel");
const conversationIdEl = $("conversationId");
const newChatBtn = $("newChatBtn");
const searchInput = $("searchInput");
const syncKnowledgeBtn = $("syncKnowledgeBtn");
const ticketTemplateBtn = $("ticketTemplateBtn");
const reloadSkillsBtn = $("reloadSkillsBtn");
const recordModeBtn = $("recordModeBtn");
const logoutBtn = $("logoutBtn");
const settingsBtn = $("settingsBtn");
const settingsMenu = $("settingsMenu");
const userChipBtn = $("userChipBtn");
const userMenu = $("userMenu");
const sidebar = $("sidebar");
const scrim = $("scrim");
const menuToggle = $("menuToggle");
const toastStack = $("toastStack");
const adminBoardBtn = $("adminBoardBtn");
const adminDashboard = $("adminDashboard");
const adminProjectPanel = $("adminProjectPanel");
const adminProjectsBtn = $("adminProjectsBtn");
const adminLlmBtn = $("adminLlmBtn");
const adminLlmPanel = $("adminLlmPanel");
const llmConfigStatus = $("llmConfigStatus");
const llmConfigPath = $("llmConfigPath");
const llmApiKeyInput = $("llmApiKeyInput");
const llmModelInput = $("llmModelInput");
const llmBaseUrlInput = $("llmBaseUrlInput");
const llmLabelInput = $("llmLabelInput");
const saveLlmConfigBtn = $("saveLlmConfigBtn");
const closeLlmAdminBtn = $("closeLlmAdminBtn");
const tokenSummary = $("tokenSummary");
const tokenConversations = $("tokenConversations");
const tokenRuns = $("tokenRuns");
const refreshDashboardBtn = $("refreshDashboardBtn");
const closeDashboardBtn = $("closeDashboardBtn");
const closeProjectAdminBtn = $("closeProjectAdminBtn");
const projectSelectEl = $("projectSelect");
const projectConfigPanel = $("projectConfigPanel");
const projectConfigSelect = $("projectConfigSelect");
const projectCreatePanel = $("projectCreatePanel");
const createProjectBtn = $("createProjectBtn");
const cancelCreateProjectBtn = $("cancelCreateProjectBtn");
const submitCreateProjectBtn = $("submitCreateProjectBtn");
const newProjectId = $("newProjectId");
const newProjectName = $("newProjectName");
const newProjectDescription = $("newProjectDescription");
const projectMembersTags = $("projectMembersTags");
const projectMembersEditor = $("projectMembersEditor");
const saveProjectMembersBtn = $("saveProjectMembersBtn");
const projectConfigHint = $("projectConfigHint");
const projectMetaName = $("projectMetaName");
const projectMetaDescription = $("projectMetaDescription");
const projectMetaEnabled = $("projectMetaEnabled");
const projectReposEditor = $("projectReposEditor");
const projectMcpEditor = $("projectMcpEditor");
const projectAgentsTemplate = $("projectAgentsTemplate");
const projectAgentsEditor = $("projectAgentsEditor");
const saveProjectMetaBtn = $("saveProjectMetaBtn");
const loadProjectMetaDefaultBtn = $("loadProjectMetaDefaultBtn");
const saveProjectReposBtn = $("saveProjectReposBtn");
const loadProjectReposDefaultBtn = $("loadProjectReposDefaultBtn");
const saveProjectMcpBtn = $("saveProjectMcpBtn");
const loadProjectMcpDefaultBtn = $("loadProjectMcpDefaultBtn");
const saveProjectAgentsBtn = $("saveProjectAgentsBtn");
const loadProjectAgentsDefaultBtn = $("loadProjectAgentsDefaultBtn");
const reloadProjectConfigBtn = $("reloadProjectConfigBtn");
const composerZone = document.querySelector(".composer-zone");
const runApprovalBanner = $("runApprovalBanner");
const runApprovalToolHint = $("runApprovalToolHint");
const runApprovalApproveBtn = $("runApprovalApproveBtn");
const runApprovalRejectBtn = $("runApprovalRejectBtn");

/* 状态 */
let authToken = localStorage.getItem(TOKEN_KEY) || "";
let currentUser = null;
let isAdmin = false;
let llmConfigured = true;
let adminViewMode = null;
let dashboardPollTimer = null;
let currentChatId = null;
let agentConversationId = null;
let busy = false;
let chatAbortController = null;
let allChats = [];
let availableProjects = [];
let currentProjectId = localStorage.getItem(PROJECT_KEY) || "default";
let adminProjectYamlDefaults = null;
let recordMode = localStorage.getItem(RECORD_MODE_KEY) === "1";
let pendingAttachments = [];
let currentRunId = null;
let runTimelinePollTimer = null;
const LAST_CHAT_KEY = "deepticket:last_chat";

const RUN_STATUS_LABELS = {
  created: "已创建",
  queued: "排队中",
  running: "运行中",
  waiting_approval: "待审批",
  completed: "已完成",
  failed: "失败",
  blocked: "已拦截",
  cancelled: "已取消",
};

const RUN_EVENT_LABELS = {
  run_created: "Run 创建",
  run_status_changed: "状态变更",
  agent_message: "Agent 消息",
  tool_call: "Tool 调用",
  tool_result: "Tool 结果",
  policy_decision: "策略决策",
  error: "错误",
  run_completed: "Run 结束",
};

function syncAppState() {
  App.authToken = authToken;
  App.currentProjectId = currentProjectId;
  App.isAdmin = isAdmin;
  App.llmConfigured = llmConfigured;
  App.adminViewMode = adminViewMode;
  App.currentChatId = currentChatId;
}

function adminDom() {
  return {
    adminDashboard,
    adminProjectPanel,
    adminLlmPanel,
    messagesEl,
    composerZone,
    chatTitleEl,
    conversationIdEl,
    adminBoardBtn,
    adminProjectsBtn,
    adminLlmBtn,
    closeSidebarMobile,
  };
}

function closeAdminView({ restoreChat = true } = {}) {
  adminViewMode = null;
  App.adminViewMode = null;
  hideAdminPanels(adminDom());
  if (dashboardPollTimer) {
    window.clearInterval(dashboardPollTimer);
    dashboardPollTimer = null;
    App.dashboardPollTimer = null;
  }
  messagesEl.classList.remove("hidden");
  if (composerZone) composerZone.classList.remove("hidden");
  updateAdminNavActive(adminDom());
  if (!restoreChat) return;
  if (currentChatId) {
    openChat(currentChatId).catch(() => clearChatPanel());
  } else {
    clearChatPanel();
  }
}

function projectQuery(extra = "") {
  const join = extra.includes("?") ? "&" : "?";
  return `${extra}${join}project_id=${encodeURIComponent(currentProjectId || "default")}`;
}

async function loadProjects() {
  const resp = await apiFetch("/api/projects");
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "加载项目失败");
  availableProjects = data.projects || [];
  if (!availableProjects.some((item) => item.id === currentProjectId)) {
    currentProjectId = availableProjects[0]?.id || "default";
    localStorage.setItem(PROJECT_KEY, currentProjectId);
  }
  if (projectSelectEl) {
    projectSelectEl.innerHTML = availableProjects
      .map(
        (item) =>
          `<option value="${escapeHtml(item.id)}"${item.id === currentProjectId ? " selected" : ""}>${escapeHtml(item.name)} (${escapeHtml(item.id)})</option>`,
      )
      .join("");
  }
}

async function switchProject(projectId) {
  if (!projectId || projectId === currentProjectId) return;
  currentProjectId = projectId;
  localStorage.setItem(PROJECT_KEY, currentProjectId);
  currentChatId = null;
  agentConversationId = null;
  clearChatPanel();
  await loadHealth();
  await refreshChats();
}

function syncRecordModeUi() {
  if (!recordModeBtn) return;
  recordModeBtn.classList.toggle("active", recordMode);
  recordModeBtn.setAttribute("aria-pressed", recordMode ? "true" : "false");
}

syncRecordModeUi();

if (!authToken) window.location.replace("/");

/* --------------------------------------------------------------------------
 * 工具
 * ------------------------------------------------------------------------ */

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  return headers;
}

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  if (resp.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    window.location.replace("/");
    throw new Error("登录已过期");
  }
  return resp;
}

function toast(message, type = "info", duration = 2600) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-dot"></span><span>${escapeHtml(message)}</span>`;
  toastStack.appendChild(el);
  window.setTimeout(() => {
    el.classList.add("out");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  }, duration);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} 天前`;
  return new Date(then).toLocaleDateString("zh-CN");
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = ICONS.check;
    btn.style.color = "var(--success)";
    window.setTimeout(() => {
      btn.innerHTML = orig;
      btn.style.color = "";
    }, 1300);
  }
}

/* --------------------------------------------------------------------------
 * 状态展示
 * ------------------------------------------------------------------------ */

function setStatus(text, mode = "ready") {
  statusEl.textContent = text;
  statusPill.classList.remove("ready", "busy", "error");
  statusPill.classList.add(mode === "busy" ? "busy" : mode === "error" ? "error" : "ready");
}

function updateRunStatusPill(run) {
  if (!runStatusPill || !runStatusText) return;
  if (!run || !run.status) {
    runStatusPill.classList.add("hidden");
    runStatusPill.classList.remove("running", "failed", "completed", "cancelled", "waiting");
    return;
  }
  const label = RUN_STATUS_LABELS[run.status] || run.status;
  runStatusText.textContent = `Run · ${label}`;
  runStatusPill.classList.remove("hidden", "running", "failed", "completed", "cancelled", "waiting");
  if (run.status === "running" || run.status === "queued" || run.status === "created") {
    runStatusPill.classList.add("running");
  } else if (run.status === "failed") {
    runStatusPill.classList.add("failed");
  } else if (run.status === "blocked") {
    runStatusPill.classList.add("failed");
  } else if (run.status === "completed") {
    runStatusPill.classList.add("completed");
  } else if (run.status === "cancelled") {
    runStatusPill.classList.add("cancelled");
  } else if (run.status === "waiting_approval") {
    runStatusPill.classList.add("waiting");
  }
}

async function fetchRun(runId) {
  if (!runId) return null;
  const resp = await apiFetch(projectQuery(`/api/runs/${runId}`));
  const data = await resp.json();
  if (!resp.ok) return null;
  return data;
}

async function postRunApproval(runId, action, reason = "") {
  const resp = await apiFetch(projectQuery(`/api/runs/${runId}/${action}`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `${action} 失败`);
  }
  return data;
}

function hideRunApprovalBanner() {
  if (runApprovalBanner) {
    runApprovalBanner.classList.add("hidden");
    delete runApprovalBanner.dataset.runId;
  }
}

function showRunApprovalBanner(run, pendingApproval) {
  if (!runApprovalBanner || !run?.run_id) return;
  currentRunId = run.run_id;
  updateRunStatusPill(run);
  const tool = pendingApproval?.tool_name || "tool";
  const command = pendingApproval?.arguments?.command;
  const extra = command ? ` · ${command}` : "";
  if (runApprovalToolHint) {
    runApprovalToolHint.textContent = `工具 ${tool}${extra}`;
  }
  runApprovalBanner.dataset.runId = run.run_id;
  runApprovalBanner.classList.remove("hidden");
  setComposerEnabled(false);
  setStatus("等待审批", "busy");
}

function syncRunApprovalFromStatus(status) {
  const inv = status?.investigation_run;
  if (inv?.status === "waiting_approval" && status?.pending_approval) {
    showRunApprovalBanner(inv, status.pending_approval);
    return true;
  }
  if (status?.agent_run_status !== "waiting_approval") {
    hideRunApprovalBanner();
  }
  return false;
}

async function handleRunApprovalAction(runId, action, { baselineCount = null } = {}) {
  if (!runId) return;
  const approveBtn = runApprovalApproveBtn;
  const rejectBtn = runApprovalRejectBtn;
  if (approveBtn) approveBtn.disabled = true;
  if (rejectBtn) rejectBtn.disabled = true;
  try {
    await postRunApproval(runId, action);
    hideRunApprovalBanner();
    if (action === "approve") {
      setBusy(true);
      setStatus("已批准，Agent 继续执行…", "busy");
      setComposerEnabled(false);
      if (currentChatId) {
        const countBaseline =
          baselineCount ?? document.querySelectorAll("#history .msg").length;
        const updated = await waitForAssistantReply(currentChatId, countBaseline, {
          maxAttempts: 90,
        });
        if (updated && currentChatId) {
          renderHistory(updated.messages || []);
          await refreshChats();
          if (updated.title) chatTitleEl.textContent = updated.title;
          toast("Agent 已继续执行", "success");
        }
      }
      setStatus("就绪");
    } else {
      setStatus("已拒绝", "error");
      toast("已拒绝工具调用", "info");
      const detail = await fetchRun(runId);
      if (detail?.run) updateRunStatusPill(detail.run);
      setComposerEnabled(true);
    }
  } catch (err) {
    toast(err.message || "审批操作失败", "error");
    throw err;
  } finally {
    if (approveBtn) approveBtn.disabled = false;
    if (rejectBtn) rejectBtn.disabled = false;
    if (action === "approve") {
      setBusy(false);
      setComposerEnabled(true);
    }
  }
}

async function pollChatStatusForApproval(chatId) {
  if (!chatId) return false;
  try {
    const statusResp = await apiFetch(projectQuery(`/api/chats/${chatId}/status`));
    const statusData = await statusResp.json();
    if (!statusResp.ok) return false;
    const status = statusData.status || {};
    if (status.investigation_run) {
      currentRunId = status.investigation_run.run_id || currentRunId;
      updateRunStatusPill(status.investigation_run);
    }
    return syncRunApprovalFromStatus(status);
  } catch {
    return false;
  }
}

async function fetchRunEvents(runId, afterSeq = 0) {
  if (!runId) return [];
  const resp = await apiFetch(
    projectQuery(`/api/runs/${runId}/events?after_seq=${afterSeq}&limit=200`),
  );
  const data = await resp.json();
  if (!resp.ok) return [];
  return data.events || [];
}

function runEventToActivity(event) {
  const type = event?.type || "";
  const payload = event?.payload || {};
  if (type === "tool_call") {
    const tool = payload.tool || "tool";
    const server = payload.mcp_server ? ` @ ${payload.mcp_server}` : "";
    return { text: `调用 ${tool}${server}`, kind: "terminal" };
  }
  if (type === "tool_result") {
    const summary = payload.summary || payload.text_preview || "工具返回";
    return { text: summary, kind: payload.status === "error" ? "error" : "default" };
  }
  if (type === "policy_decision") {
    const tool = payload.tool || "tool";
    const decision = payload.decision || "unknown";
    return {
      text: `策略 ${decision}: ${tool}`,
      kind: decision === "deny" ? "error" : "system",
    };
  }
  if (type === "error") {
    return { text: payload.message || "运行错误", kind: "error" };
  }
  if (type === "agent_message") {
    return { text: payload.text_preview || "Agent 消息", kind: "think" };
  }
  if (type === "run_status_changed") {
    const from = payload.from || "?";
    const to = payload.to || "?";
    return { text: `Run 状态 ${from} → ${to}`, kind: "system" };
  }
  return null;
}

function rememberOpenChat(chatId) {
  if (!chatId || !currentProjectId) return;
  sessionStorage.setItem(LAST_CHAT_KEY, `${currentProjectId}:${chatId}`);
}

function chatNeedsResume(chat, status) {
  const inv = status?.investigation_run;
  if (
    inv
    && ["running", "queued", "created", "waiting_approval"].includes(inv.status)
  ) {
    const messages = chat?.messages || [];
    const last = messages[messages.length - 1];
    if (inv.status === "waiting_approval") return true;
    return last?.role === "user";
  }
  const messages = chat?.messages || [];
  if (!messages.length) return false;
  const last = messages[messages.length - 1];
  return last.role === "user" && chat.agent_run_status === "running";
}

async function restoreLastOpenChat() {
  const raw = sessionStorage.getItem(LAST_CHAT_KEY);
  if (!raw) return;
  const [projectId, chatId] = raw.split(":", 2);
  if (!projectId || !chatId || projectId !== currentProjectId) return;
  if (!allChats.some((item) => item.chat_id === chatId)) return;
  await openChat(chatId);
}

function renderRunTimeline(listEl, metaEl, events, run) {
  if (!listEl) return;
  if (metaEl && run) {
    metaEl.innerHTML = `
      <div class="run-timeline-head">
        <span class="run-timeline-id">#${escapeHtml(String(run.run_id || "").slice(0, 8))}</span>
        <span class="run-timeline-status">${escapeHtml(RUN_STATUS_LABELS[run.status] || run.status || "—")}</span>
      </div>`;
  }
  if (!events.length) {
    listEl.innerHTML = `<div class="run-timeline-empty">暂无 Run 事件</div>`;
    return;
  }
  listEl.innerHTML = events
    .map((event) => {
      const type = event.type || "event";
      const label = RUN_EVENT_LABELS[type] || type;
      const payload = event.payload || {};
      const detail =
        payload.text_preview ||
        payload.summary ||
        payload.message ||
        payload.tool ||
        payload.decision ||
        (payload.from && payload.to ? `${payload.from} → ${payload.to}` : "");
      return `<div class="run-timeline-item" data-type="${escapeHtml(type)}">
        <div class="run-timeline-item-head">
          <span class="run-timeline-seq">#${Number(event.seq || 0)}</span>
          <span class="run-timeline-type">${escapeHtml(label)}</span>
        </div>
        <div class="run-timeline-detail">${escapeHtml(String(detail || ""))}</div>
      </div>`;
    })
    .join("");
}

function bindThinkingTabs(root) {
  const tabs = root.querySelectorAll(".thinking-tab");
  const panels = root.querySelectorAll(".thinking-panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", (event) => {
      event.stopPropagation();
      const name = tab.dataset.tab;
      tabs.forEach((item) => item.classList.toggle("active", item === tab));
      panels.forEach((panel) => {
        panel.classList.toggle("hidden", panel.dataset.panel !== name);
      });
    });
  });
}

function renderRunApprovalActions(metaEl, run, pendingApproval) {
  if (!metaEl || !run || run.status !== "waiting_approval") return;
  const tool = pendingApproval?.tool_name || "tool";
  metaEl.insertAdjacentHTML(
    "beforeend",
    `<div class="run-approval-actions">
      <span class="run-approval-hint">待审批工具：<code>${escapeHtml(tool)}</code></span>
      <button type="button" class="btn btn-primary btn-sm" data-run-approve="${escapeHtml(run.run_id)}">批准</button>
      <button type="button" class="btn btn-secondary btn-sm" data-run-reject="${escapeHtml(run.run_id)}">拒绝</button>
    </div>`,
  );
}

function bindRunApprovalActions(root, metaEl) {
  root.querySelectorAll("[data-run-approve]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const runId = btn.getAttribute("data-run-approve");
      if (!runId) return;
      btn.disabled = true;
      try {
        await handleRunApprovalAction(runId, "approve");
      } catch {
        /* toast 已在 handleRunApprovalAction */
      } finally {
        btn.disabled = false;
      }
    });
  });
  root.querySelectorAll("[data-run-reject]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const runId = btn.getAttribute("data-run-reject");
      if (!runId) return;
      btn.disabled = true;
      try {
        await handleRunApprovalAction(runId, "reject");
      } catch {
        /* toast 已在 handleRunApprovalAction */
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function bindRunDetailsToggle(root, { detailsPanelEl, detailsBtnEl, onOpen }) {
  if (!detailsBtnEl || !detailsPanelEl) return;
  detailsBtnEl.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = detailsPanelEl.classList.toggle("hidden");
    detailsBtnEl.classList.toggle("active", !open);
    detailsBtnEl.setAttribute("aria-expanded", open ? "false" : "true");
    if (!open && typeof onOpen === "function") onOpen();
  });
}

function attachRunTimelineController(root, { timelineListEl, timelineMetaEl, getRun }) {
  let afterSeq = 0;
  let polling = false;

  const refresh = async () => {
    const runHint = typeof getRun === "function" ? getRun() : null;
    const runId = runHint?.run_id || currentRunId;
    if (!runId) return;
    const detail = await fetchRun(runId);
    const run = detail?.run || runHint;
    const events = await fetchRunEvents(runId, afterSeq);
    if (events.length) {
      afterSeq = Math.max(afterSeq, ...events.map((item) => Number(item.seq || 0)));
      const existing = root.__runEvents || [];
      root.__runEvents = existing.concat(events);
    }
    renderRunTimeline(timelineListEl, timelineMetaEl, root.__runEvents || [], run);
    if (run?.status === "waiting_approval" && detail?.pending_approval && timelineMetaEl) {
      if (!timelineMetaEl.querySelector(".run-approval-actions")) {
        renderRunApprovalActions(timelineMetaEl, run, detail.pending_approval);
        bindRunApprovalActions(root, timelineMetaEl);
      }
    }
    if (run && !["running", "queued", "created", "waiting_approval"].includes(run.status)) {
      stop();
    }
  };

  const start = () => {
    if (polling) return;
    polling = true;
    root.__runEvents = [];
    afterSeq = 0;
    refresh();
    runTimelinePollTimer = window.setInterval(refresh, 2000);
  };

  const stop = () => {
    polling = false;
    if (runTimelinePollTimer) {
      window.clearInterval(runTimelinePollTimer);
      runTimelinePollTimer = null;
    }
  };

  return { refresh, start, stop };
}

function setBusy(nextBusy) {
  busy = nextBusy;
  sendBtn.disabled = nextBusy || !currentChatId;
  stopBtn.classList.toggle("hidden", !nextBusy);
  newChatBtn.disabled = nextBusy;
}

function setComposerEnabled(enabled) {
  promptEl.disabled = !enabled;
  if (attachBtnEl) attachBtnEl.disabled = !enabled;
  sendBtn.disabled = !enabled || busy;
}

function updateEmptyState() {
  const hasMessages = messagesInner.querySelector(".msg");
  emptyStateEl.style.display = hasMessages ? "none" : "";
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function updateConversationMeta() {
  const chat = allChats.find((c) => c.chat_id === currentChatId);
  const tokenTotal = chat?.token_usage?.total_tokens;
  const parts = [];
  if (agentConversationId) {
    parts.push(`Agent · ${agentConversationId.slice(0, 12)}…`);
  }
  if (tokenTotal) {
    parts.push(`${formatToken(tokenTotal)} tokens`);
  }
  conversationIdEl.textContent = parts.join(" · ");
}

function autoResizePrompt() {
  promptEl.style.height = "auto";
  promptEl.style.height = `${Math.min(promptEl.scrollHeight, 200)}px`;
}

/* --------------------------------------------------------------------------
 * 消息渲染
 * ------------------------------------------------------------------------ */

function fillMessageAvatar(avatar, role) {
  avatar.replaceChildren();
  if (role === "user") {
    avatar.textContent = (currentUser?.username?.[0] || "U").toUpperCase();
    return;
  }
  const img = document.createElement("img");
  img.src = MASCOT_ICON;
  img.alt = "DeepTicket AI";
  img.width = 28;
  img.height = 28;
  avatar.appendChild(img);
}

function createMessageRow(role) {
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  fillMessageAvatar(avatar, role);
  const body = document.createElement("div");
  body.className = "msg-body";
  const content = document.createElement("div");
  content.className = "msg-content";
  body.appendChild(content);
  row.appendChild(avatar);
  row.appendChild(body);
  messagesInner.appendChild(row);
  updateEmptyState();
  scrollToBottom();
  return { row, body, content };
}

function displayImageUrl(url) {
  if (!url) return url;
  if (url.startsWith("/")) return url;
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.pathname.startsWith("/api/uploads/images/")) {
      return parsed.pathname;
    }
  } catch {
    return url;
  }
  return url;
}

function addUserMessage(text, imageUrls = []) {
  const { content } = createMessageRow("user");
  content.textContent = text;
  if (imageUrls.length) {
    const gallery = document.createElement("div");
    gallery.className = "msg-attachments";
    imageUrls.forEach((url) => {
      const img = document.createElement("img");
      img.src = displayImageUrl(url);
      img.alt = "截图";
      img.loading = "lazy";
      gallery.appendChild(img);
    });
    content.appendChild(gallery);
  }
  scrollToBottom();
}

function renderAttachmentStrip() {
  if (!attachmentStripEl) return;
  attachmentStripEl.innerHTML = "";
  if (!pendingAttachments.length) {
    attachmentStripEl.classList.add("hidden");
    return;
  }
  attachmentStripEl.classList.remove("hidden");
  pendingAttachments.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";
    const img = document.createElement("img");
    img.src = item.preview;
    img.alt = item.name || "截图";
    const meta = document.createElement("span");
    meta.className = "attachment-name";
    meta.textContent = item.name || "截图";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "attachment-remove";
    remove.title = "移除";
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      pendingAttachments = pendingAttachments.filter((entry) => entry.id !== item.id);
      renderAttachmentStrip();
    });
    chip.append(img, meta, remove);
    attachmentStripEl.appendChild(chip);
  });
}

function clearAttachments() {
  pendingAttachments = [];
  renderAttachmentStrip();
}

async function uploadImageFile(file) {
  const form = new FormData();
  form.append("file", file);
  const resp = await apiFetch("/api/uploads/images", {
    method: "POST",
    body: form,
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || "截图上传失败");
  }
  const preview = URL.createObjectURL(file);
  pendingAttachments.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    url: data.url,
    preview,
    name: data.name || file.name || "截图",
  });
  renderAttachmentStrip();
}

async function addImageFiles(files) {
  const list = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  if (!list.length) {
    toast("请选择图片文件", "info");
    return;
  }
  for (const file of list) {
    try {
      await uploadImageFile(file);
    } catch (err) {
      toast(err.message || "截图上传失败", "error");
      break;
    }
  }
}

async function handleComposerPaste(event) {
  const items = event.clipboardData?.items;
  if (!items) return;
  const files = [];
  for (const item of items) {
    if (item.kind === "file" && item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file) files.push(file);
    }
  }
  if (!files.length) return;
  event.preventDefault();
  await addImageFiles(files);
}

function addToolbar(body, rawText) {
  const bar = document.createElement("div");
  bar.className = "msg-toolbar";
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "icon-btn";
  copyBtn.title = "复制";
  copyBtn.innerHTML = ICONS.copy;
  copyBtn.addEventListener("click", () => copyText(rawText, copyBtn));
  bar.appendChild(copyBtn);
  body.appendChild(bar);
}

function shouldShowConfidence(confidence, activities) {
  if (!confidence || confidence.score == null) return false;
  if (confidence.applicable === false) return false;
  if (Array.isArray(activities) && activities.length) {
    return activities.some((item) => CONFIDENCE_ANALYSIS_KINDS.has(item.kind || "default"));
  }
  return confidence.applicable === true;
}

function renderConfidenceBadge(confidence) {
  if (!confidence || confidence.score == null) return null;
  const badge = document.createElement("div");
  const level = confidence.level || "medium";
  badge.className = `confidence-badge confidence-${level}`;
  const reasons = Array.isArray(confidence.reasons) ? confidence.reasons : [];
  if (reasons.length) badge.title = reasons.join("\n");
  badge.innerHTML = `<span class="confidence-label">置信度</span><strong>${escapeHtml(confidence.label || "—")}</strong><span class="confidence-score">${confidence.score}%</span>`;
  return badge;
}

function attachConfidence(body, confidence, activities = null) {
  const existing = body.querySelector(".confidence-badge");
  if (existing) existing.remove();
  if (!shouldShowConfidence(confidence, activities)) return;
  const badge = renderConfidenceBadge(confidence);
  if (badge) body.appendChild(badge);
}

function createAssistantShell(withThinking, options = {}) {
  const { row, body, content } = createMessageRow("assistant");
  let thinking = null;
  if (withThinking) {
    thinking = createThinkingBlock(options);
    body.insertBefore(thinking.root, content);
    scrollToBottom();
  }
  return { row, body, content, thinking };
}

function bindCodeCopy(container) {
  container.querySelectorAll(".md-copy").forEach((btn) => {
    btn.addEventListener("click", () => {
      const pre = btn.closest(".md-pre");
      const raw = pre?.dataset.code ?? pre?.querySelector("code")?.textContent ?? "";
      copyText(raw, null);
      const orig = btn.textContent;
      btn.textContent = "已复制";
      btn.classList.add("ok");
      window.setTimeout(() => {
        btn.textContent = orig;
        btn.classList.remove("ok");
      }, 1300);
    });
  });
}

/* Thinking 块 — 展示 Agent 实时活动（来自 SSE activity 事件） */

function createThinkingStepEl(item, { isLast, iconFor }) {
  const step = document.createElement("div");
  step.className = "thinking-step";
  if (item.kind === "evidence") step.classList.add("evidence");
  if (item.kind === "handoff") step.classList.add("handoff");
  if (item.kind === "error") step.classList.add("error");
  step.classList.add(isLast ? "current" : "done");
  step.innerHTML = `<span class="step-icon">${iconFor(item.kind)}</span><span class="step-text">${escapeHtml(item.text)}</span>`;
  return step;
}

function updateThinkingScrollState(bodyEl, tabScrollEl) {
  if (bodyEl) {
    const { scrollTop, scrollHeight, clientHeight } = bodyEl;
    bodyEl.classList.toggle("can-scroll-top", scrollTop > 6);
    bodyEl.classList.toggle("can-scroll-bottom", scrollTop + clientHeight < scrollHeight - 6);
  }
  if (tabScrollEl) {
    const { scrollLeft, scrollWidth, clientWidth } = tabScrollEl;
    tabScrollEl.classList.toggle("can-scroll-end", scrollLeft + clientWidth < scrollWidth - 6);
  }
}

function scrollThinkingPanel({ bodyEl, tabScrollEl, stickBody = true }) {
  if (bodyEl && stickBody) {
    bodyEl.scrollTop = bodyEl.scrollHeight;
  }
  if (tabScrollEl) {
    tabScrollEl.scrollLeft = tabScrollEl.scrollWidth;
  }
  updateThinkingScrollState(bodyEl, tabScrollEl);
}

function bindThinkingInteractions(root, { bodyEl, tabScrollEl, toggleEl }) {
  let stickBody = true;
  let tabDragged = false;
  let tabDragStartX = 0;

  bodyEl.addEventListener(
    "scroll",
    () => {
      stickBody = bodyEl.scrollHeight - bodyEl.scrollTop - bodyEl.clientHeight < 28;
      updateThinkingScrollState(bodyEl, tabScrollEl);
    },
    { passive: true },
  );

  tabScrollEl.addEventListener(
    "scroll",
    () => updateThinkingScrollState(bodyEl, tabScrollEl),
    { passive: true },
  );

  tabScrollEl.addEventListener("wheel", (event) => {
    if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
    event.preventDefault();
    tabScrollEl.scrollLeft += event.deltaY;
  }, { passive: false });

  tabScrollEl.addEventListener("pointerdown", (event) => {
    tabDragStartX = event.clientX;
    tabDragged = false;
  });

  tabScrollEl.addEventListener("pointermove", (event) => {
    if (Math.abs(event.clientX - tabDragStartX) > 8) tabDragged = true;
  });

  toggleEl.addEventListener("click", (event) => {
    if (tabDragged && event.target.closest(".thinking-tab-scroll")) {
      event.preventDefault();
      tabDragged = false;
      return;
    }
    root.classList.toggle("collapsed");
    if (!root.classList.contains("collapsed")) {
      requestAnimationFrame(() => scrollThinkingPanel({ bodyEl, tabScrollEl, stickBody: true }));
    }
  });

  return {
    shouldStickBody: () => stickBody,
    resetStickBody: () => {
      stickBody = true;
    },
  };
}

function syncThinkingSteps(stepsEl, activities, iconFor, { markLastCurrent = true } = {}) {
  const iconFn = iconFor;
  if (!activities.length) {
    stepsEl.innerHTML = `<div class="thinking-step current"><span class="step-icon">${iconFn("system")}</span><span class="step-text">等待 Agent 响应…</span></div>`;
    return;
  }

  while (stepsEl.children.length > activities.length) {
    stepsEl.lastElementChild?.remove();
  }

  activities.forEach((item, idx) => {
    const isLast = idx === activities.length - 1;
    let step = stepsEl.children[idx];
    if (!step) {
      step = createThinkingStepEl(item, { isLast: isLast && markLastCurrent, iconFor: iconFn });
      stepsEl.appendChild(step);
      return;
    }
    step.className = "thinking-step";
    if (item.kind === "evidence") step.classList.add("evidence");
    if (item.kind === "handoff") step.classList.add("handoff");
    if (item.kind === "error") step.classList.add("error");
    step.classList.add(isLast && markLastCurrent ? "current" : "done");
    const textEl = step.querySelector(".step-text");
    if (textEl && textEl.textContent !== item.text) {
      textEl.textContent = item.text;
    }
    const iconEl = step.querySelector(".step-icon");
    if (iconEl) iconEl.textContent = iconFn(item.kind);
  });
}

function buildThinkingShell({ keepExpanded = false, label = "正在准备", showElapsed = true } = {}) {
  const root = document.createElement("div");
  root.className = "thinking active";
  if (keepExpanded) root.classList.add("record-mode");
  root.innerHTML = `
    <button type="button" class="thinking-toggle">
      <span class="thinking-spinner"></span>
      <span class="thinking-check">✓</span>
      <div class="thinking-tab-scroll" aria-label="思考步骤摘要">
        <span class="thinking-label">${escapeHtml(label)}</span>
      </div>
      <span class="thinking-step-count"></span>
      ${showElapsed ? '<span class="thinking-elapsed">0s</span>' : ""}
      <button type="button" class="thinking-run-details-btn hidden" aria-expanded="false">运行详情</button>
      <span class="thinking-chevron">${ICONS.chevron}</span>
    </button>
    <div class="thinking-body">
      <div class="thinking-panel" data-panel="steps">
        <div class="thinking-steps"></div>
        <div class="thinking-shimmer"></div>
      </div>
      <div class="thinking-panel thinking-run-details hidden" data-panel="details">
        <div class="run-timeline-meta"></div>
        <div class="run-timeline-list"></div>
      </div>
    </div>
  `;

  const toggleEl = root.querySelector(".thinking-toggle");
  const bodyEl = root.querySelector(".thinking-body");
  const tabScrollEl = root.querySelector(".thinking-tab-scroll");
  const stepsEl = root.querySelector('.thinking-panel[data-panel="steps"] .thinking-steps');
  const detailsPanelEl = root.querySelector(".thinking-run-details");
  const detailsBtnEl = root.querySelector(".thinking-run-details-btn");
  const timelineListEl = root.querySelector(".run-timeline-list");
  const timelineMetaEl = root.querySelector(".run-timeline-meta");
  const labelEl = root.querySelector(".thinking-label");
  const countEl = root.querySelector(".thinking-step-count");
  const elapsedEl = root.querySelector(".thinking-elapsed");
  const interaction = bindThinkingInteractions(root, { bodyEl, tabScrollEl, toggleEl });

  return {
    root,
    toggleEl,
    bodyEl,
    tabScrollEl,
    stepsEl,
    detailsPanelEl,
    detailsBtnEl,
    timelineListEl,
    timelineMetaEl,
    labelEl,
    countEl,
    elapsedEl,
    interaction,
  };
}

function createThinkingBlock(options = {}) {
  const keepExpanded = Boolean(options.recordMode);
  const {
    root,
    bodyEl,
    tabScrollEl,
    stepsEl,
    labelEl,
    countEl,
    elapsedEl,
    interaction,
    detailsPanelEl,
    detailsBtnEl,
    timelineListEl,
    timelineMetaEl,
  } = buildThinkingShell({ keepExpanded, label: "正在准备", showElapsed: true });

  const timelineCtl = attachRunTimelineController(root, {
    timelineListEl,
    timelineMetaEl,
    getRun: () => ({ run_id: currentRunId, status: "running" }),
  });
  bindRunDetailsToggle(root, {
    detailsPanelEl,
    detailsBtnEl,
    onOpen: () => timelineCtl.refresh(),
  });

  const activities = [];
  let currentActivity = "";
  let currentKind = "default";

  const iconFor = (kind) => ACTIVITY_ICONS[kind] || ACTIVITY_ICONS.default;

  const renderSteps = () => {
    syncThinkingSteps(stepsEl, activities, iconFor);
    if (countEl) {
      countEl.textContent = activities.length ? String(activities.length) : "";
      countEl.classList.toggle("visible", activities.length > 1);
    }
    scrollThinkingPanel({
      bodyEl,
      tabScrollEl,
      stickBody: interaction.shouldStickBody(),
    });
    scrollToBottom();
  };

  const startedAt = Date.now();
  const elapsedTimer = window.setInterval(() => {
    if (!elapsedEl) return;
    elapsedEl.textContent = `${Math.max(1, Math.round((Date.now() - startedAt) / 1000))}s`;
  }, 250);

  renderSteps();

  return {
    root,
    addActivity(text, kind = "default") {
      const next = (text || "").trim();
      if (!next || (next === currentActivity && kind === currentKind)) return;
      currentActivity = next;
      currentKind = kind;
      const last = activities[activities.length - 1];
      if (!last || last.text !== next || last.kind !== kind) {
        activities.push({ text: next, kind });
      }
      labelEl.textContent = next;
      renderSteps();
    },
    markReplyStarting() {
      this.addActivity("已获取到所有信息，开始回复", "handoff");
    },
    finish(contentStarted = false) {
      window.clearInterval(elapsedTimer);
      const seconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      if (elapsedEl) elapsedEl.textContent = `${seconds}s`;
      root.classList.remove("active");
      root.classList.add("done");
      stepsEl.querySelectorAll(".thinking-step").forEach((el) => {
        el.classList.remove("current");
        el.classList.add("done");
      });
      root.querySelector(".thinking-shimmer")?.remove();
      const stepCount = activities.length;
      if (contentStarted) {
        labelEl.textContent = stepCount
          ? `思考完成 · ${stepCount} 步 · ${seconds}s`
          : `思考用时 ${seconds}s`;
      } else {
        labelEl.textContent = stepCount
          ? `运行完成 · ${stepCount} 步 · ${seconds}s`
          : `运行 ${seconds}s`;
      }
      if (countEl) {
        countEl.textContent = stepCount ? String(stepCount) : "";
        countEl.classList.toggle("visible", stepCount > 1);
      }
      scrollThinkingPanel({ bodyEl, tabScrollEl, stickBody: true });
      if (!keepExpanded) {
        window.setTimeout(() => root.classList.add("collapsed"), contentStarted ? 2500 : 4000);
      }
    },
    stop() {
      window.clearInterval(elapsedTimer);
      timelineCtl.stop();
    },
    setRunId(runId) {
      currentRunId = runId;
      if (detailsBtnEl) detailsBtnEl.classList.remove("hidden");
      timelineCtl.start();
    },
  };
}

function createStaticThinkingBlock(activities, runId = null) {
  const safeActivities = Array.isArray(activities) ? activities : [];
  const {
    root,
    bodyEl,
    tabScrollEl,
    stepsEl,
    countEl,
    detailsPanelEl,
    detailsBtnEl,
    timelineListEl,
    timelineMetaEl,
  } = buildThinkingShell({
    keepExpanded: false,
    label: `Agent 步骤（${safeActivities.length}）`,
    showElapsed: false,
  });

  root.className = "thinking done collapsed";
  const iconFor = (kind) => ACTIVITY_ICONS[kind] || ACTIVITY_ICONS.default;
  syncThinkingSteps(stepsEl, safeActivities, iconFor, { markLastCurrent: false });
  if (countEl) {
    countEl.textContent = safeActivities.length ? String(safeActivities.length) : "";
    countEl.classList.toggle("visible", safeActivities.length > 1);
  }
  requestAnimationFrame(() => scrollThinkingPanel({ bodyEl, tabScrollEl, stickBody: false }));
  const timelineCtl = attachRunTimelineController(root, {
    timelineListEl,
    timelineMetaEl,
    getRun: () => (runId ? { run_id: runId, status: "completed" } : null),
  });
  bindRunDetailsToggle(root, {
    detailsPanelEl,
    detailsBtnEl,
    onOpen: () => {
      timelineCtl.refresh();
    },
  });
  if (runId && detailsBtnEl) {
    detailsBtnEl.classList.remove("hidden");
    timelineCtl.start();
  }
  if (runId && !safeActivities.length) {
    fetchRunEvents(runId, 0)
      .then((events) => {
        const fromEvents = events
          .map((event) => runEventToActivity(event))
          .filter(Boolean);
        if (!fromEvents.length) return;
        syncThinkingSteps(stepsEl, fromEvents, iconFor, { markLastCurrent: false });
        if (countEl) {
          countEl.textContent = String(fromEvents.length);
          countEl.classList.toggle("visible", fromEvents.length > 1);
        }
        const labelEl = root.querySelector(".thinking-label");
        if (labelEl) labelEl.textContent = `Agent 步骤（${fromEvents.length}）`;
      })
      .catch(() => {});
  }
  return root;
}

function renderHistory(messages) {
  messagesInner.querySelectorAll(".msg").forEach((el) => el.remove());
  for (const item of messages || []) {
    if (item.role === "user") {
      addUserMessage(item.content, item.image_urls || []);
    } else if (item.role === "assistant") {
      const { body, content } = createAssistantShell(false);
      if (Array.isArray(item.activities) && item.activities.length) {
        body.insertBefore(createStaticThinkingBlock(item.activities, item.run_id || null), content);
      } else if (item.run_id) {
        body.insertBefore(createStaticThinkingBlock([], item.run_id), content);
      }
      content.innerHTML = renderMarkdown(item.content);
      bindCodeCopy(content);
      addToolbar(body, item.content);
      attachConfidence(body, item.confidence, item.activities);
    }
  }
  updateEmptyState();
  scrollToBottom();
}

function clearChatPanel() {
  currentChatId = null;
  agentConversationId = null;
  currentRunId = null;
  updateRunStatusPill(null);
  chatTitleEl.textContent = "选择或新建对话";
  updateConversationMeta();
  messagesInner.querySelectorAll(".msg").forEach((el) => el.remove());
  updateEmptyState();
  clearAttachments();
  setComposerEnabled(false);
  renderChatList();
}

/* --------------------------------------------------------------------------
 * 会话列表
 * ------------------------------------------------------------------------ */

function renderChatList() {
  const query = searchInput.value.trim().toLowerCase();
  const visible = query
    ? allChats.filter((c) => {
        const title = (c.title || "").toLowerCase();
        const blob = (c.search_text || "").toLowerCase();
        return title.includes(query) || blob.includes(query);
      })
    : allChats;

  chatListEl.innerHTML = "";
  if (!allChats.length) {
    chatListEl.innerHTML = '<div class="chat-list-empty">暂无对话<br />点击上方「新对话」开始</div>';
    return;
  }
  if (!visible.length) {
    chatListEl.innerHTML = '<div class="chat-list-empty">没有匹配的对话</div>';
    return;
  }

  for (const chat of visible) {
    const item = document.createElement("div");
    item.className = "chat-item";
    if (chat.chat_id === currentChatId) item.classList.add("active");
    item.dataset.chatId = chat.chat_id;

    const body = document.createElement("div");
    body.className = "chat-item-body";
    const title = document.createElement("span");
    title.className = "chat-item-title";
    title.textContent = chat.title || "新会话";
    const time = document.createElement("span");
    time.className = "chat-item-time";
    time.textContent = timeAgo(chat.updated_at);
    const tokens = document.createElement("span");
    tokens.className = "chat-item-tokens";
    const tokenTotal = chat.token_usage?.total_tokens;
    tokens.textContent = tokenTotal ? `${formatToken(tokenTotal)} tokens` : "";
    body.appendChild(title);
    body.appendChild(time);
    if (tokenTotal) body.appendChild(tokens);

    const actions = document.createElement("div");
    actions.className = "chat-item-actions";

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "icon-btn";
    renameBtn.title = "重命名";
    renameBtn.innerHTML = ICONS.edit;
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      startRename(item, chat, title);
    });

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "icon-btn danger";
    delBtn.title = "删除";
    delBtn.innerHTML = ICONS.trash;
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      confirmDelete(chat.chat_id);
    });

    actions.appendChild(renameBtn);
    actions.appendChild(delBtn);
    item.appendChild(body);
    item.appendChild(actions);
    item.addEventListener("click", () => openChat(chat.chat_id));
    chatListEl.appendChild(item);
  }
}

function startRename(item, chat, titleEl) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "chat-rename-input";
  input.value = chat.title || "新会话";
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  async function commit(save) {
    if (done) return;
    done = true;
    const next = input.value.trim();
    if (save && next && next !== chat.title) {
      try {
        const resp = await apiFetch(projectQuery(`/api/chats/${chat.chat_id}`), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: next }),
        });
        if (resp.ok) {
          chat.title = next;
          if (currentChatId === chat.chat_id) chatTitleEl.textContent = next;
          toast("已重命名", "success");
        } else {
          toast("重命名失败", "error");
        }
      } catch {
        toast("重命名失败", "error");
      }
    }
    await refreshChats();
  }

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") commit(true);
    if (e.key === "Escape") commit(false);
    e.stopPropagation();
  });
  input.addEventListener("blur", () => commit(true));
  input.addEventListener("click", (e) => e.stopPropagation());
}

async function confirmDelete(chatId) {
  const chat = allChats.find((c) => c.chat_id === chatId);
  if (!window.confirm(`删除对话「${chat?.title || "新会话"}」？此操作不可撤销。`)) return;
  try {
    const resp = await apiFetch(projectQuery(`/api/chats/${chatId}`), { method: "DELETE" });
    if (!resp.ok) throw new Error();
    allChats = allChats.filter((c) => c.chat_id !== chatId);
    if (currentChatId === chatId) clearChatPanel();
    else renderChatList();
    toast("已删除", "success");
  } catch {
    toast("删除失败", "error");
  }
}

async function refreshChats() {
  const resp = await apiFetch(projectQuery("/api/chats"));
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "加载对话失败");
  allChats = data.chats || [];
  renderChatList();
}

/* --------------------------------------------------------------------------
 * 会话打开 / 创建
 * ------------------------------------------------------------------------ */

async function openChat(chatId) {
  if (busy) return;
  if (adminViewMode) {
    closeAdminView({ restoreChat: false });
  }
  const resp = await apiFetch(projectQuery(`/api/chats/${chatId}`));
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "打开对话失败");

  currentChatId = data.chat.chat_id;
  rememberOpenChat(currentChatId);
  agentConversationId = data.chat.agent_conversation_id || null;
  chatTitleEl.textContent = data.chat.title || "新会话";
  const chatIdx = allChats.findIndex((c) => c.chat_id === chatId);
  if (chatIdx >= 0) {
    allChats[chatIdx] = {
      ...allChats[chatIdx],
      title: data.chat.title || allChats[chatIdx].title,
      token_usage: data.chat.token_usage || allChats[chatIdx].token_usage,
    };
  }
  renderHistory(data.chat.messages || []);
  updateConversationMeta();
  setComposerEnabled(true);
  renderChatList();
  setStatus("就绪");
  try {
    const statusResp = await apiFetch(projectQuery(`/api/chats/${chatId}/status`));
    const statusData = await statusResp.json();
    const status = statusResp.ok ? statusData.status || {} : {};
    if (status.investigation_run) {
      currentRunId = status.investigation_run.run_id || null;
      updateRunStatusPill(status.investigation_run);
    } else {
      updateRunStatusPill(null);
    }
    syncRunApprovalFromStatus(status);
    closeSidebarMobile();
    promptEl.focus();
    resumePendingAssistant(data.chat, status).catch((err) => toast(err.message, "error"));
  } catch {
    updateRunStatusPill(null);
    closeSidebarMobile();
    promptEl.focus();
  }
}

async function createChat() {
  if (busy) return;
  if (chatAbortController) {
    chatAbortController.abort();
    chatAbortController = null;
  }
  const resp = await apiFetch("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: "新会话", project_id: currentProjectId }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "创建对话失败");
  await refreshChats();
  await openChat(data.chat.chat_id);
}

/* --------------------------------------------------------------------------
 * 发送消息（流式 + Markdown 增量渲染）
 * ------------------------------------------------------------------------ */

async function pollChatForReply(chatId, baselineCount, { maxAttempts = 15 } = {}) {
  let delayMs = 1000;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    delayMs = Math.min(Math.round(delayMs * 1.4), 8000);
    const statusResp = await apiFetch(projectQuery(`/api/chats/${chatId}/status`));
    const statusData = await statusResp.json();
    if (!statusResp.ok) continue;
    const status = statusData.status || {};
    if (status.investigation_run) {
      currentRunId = status.investigation_run.run_id || currentRunId;
      updateRunStatusPill(status.investigation_run);
    }
    if (
      status.agent_run_status === "waiting_approval"
      || status.investigation_run?.status === "waiting_approval"
    ) {
      syncRunApprovalFromStatus(status);
      return { chat: null, message: null, waitingApproval: true };
    }
    const latest = status.latest_message;
    const messageCount = Number(status.message_count || 0);
    if (status.agent_run_status === "failed") {
      return { chat: null, message: latest || null, failed: true };
    }
    if (messageCount > baselineCount && latest?.role === "assistant" && latest.content) {
      const resp = await apiFetch(projectQuery(`/api/chats/${chatId}`));
      const data = await resp.json();
      if (!resp.ok) continue;
      const chat = data.chat || {};
      const messages = chat.messages || [];
      const last = messages[messages.length - 1];
      if (last?.role === "assistant" && last.content) return { chat, message: last };
      return { chat, message: latest };
    }
    if (status.agent_run_status === "idle" && messageCount > baselineCount && latest?.role === "assistant") {
      const resp = await apiFetch(projectQuery(`/api/chats/${chatId}`));
      const data = await resp.json();
      if (!resp.ok) continue;
      const chat = data.chat || {};
      const messages = chat.messages || [];
      const last = messages[messages.length - 1];
      if (last?.role === "assistant") return { chat, message: last };
    }
  }
  return null;
}

async function waitForAssistantReply(chatId, baselineCount) {
  const result = await pollChatForReply(chatId, baselineCount, { maxAttempts: 90 });
  return result?.chat || null;
}

function chatNeedsAssistantWait(chat) {
  const messages = chat?.messages || [];
  if (!messages.length) return false;
  const last = messages[messages.length - 1];
  return last.role === "user" && chat.agent_run_status === "running";
}

async function resumePendingAssistant(chat, status = {}) {
  if (!chatNeedsResume(chat, status)) return;
  const invRun = status.investigation_run || null;
  const runId = invRun?.run_id || null;
  if (runId) {
    currentRunId = runId;
    updateRunStatusPill(invRun);
  }

  const baselineCount = (chat.messages || []).length;
  setBusy(true);
  setStatus(
    invRun?.status === "waiting_approval" ? "等待审批…" : "Agent 仍在分析…",
    "busy",
  );
  const { body, content, thinking } = createAssistantShell(true, { recordMode });
  content.classList.add("placeholder");
  if (invRun?.status === "waiting_approval") {
    content.textContent = "工具调用待审批，请展开「运行详情」批准或拒绝。";
  } else {
    content.textContent = "Agent 仍在后台分析，正在从服务端恢复进度…";
  }
  thinking.addActivity("页面已刷新，正在恢复 Run 进度…", "system");
  if (runId) {
    thinking.setRunId(runId);
  }

  let afterSeq = 0;
  const seenActivityKeys = new Set();
  const syncRunEvents = async () => {
    if (!runId) return;
    const events = await fetchRunEvents(runId, afterSeq);
    if (!events.length) return;
    afterSeq = Math.max(afterSeq, ...events.map((item) => Number(item.seq || 0)));
    for (const event of events) {
      const activity = runEventToActivity(event);
      if (!activity) continue;
      const key = `${event.seq || 0}:${activity.text}:${activity.kind}`;
      if (seenActivityKeys.has(key)) continue;
      seenActivityKeys.add(key);
      thinking.addActivity(activity.text, activity.kind);
    }
  };

  await syncRunEvents();
  const eventPollTimer = window.setInterval(() => {
    syncRunEvents().catch(() => {});
  }, 2000);

  if (invRun?.status === "waiting_approval") {
    syncRunApprovalFromStatus(status);
    window.clearInterval(eventPollTimer);
    setBusy(false);
    return;
  }

  try {
    const updated = await waitForAssistantReply(chat.chat_id, baselineCount);
    if (!updated || currentChatId !== chat.chat_id) return;
    renderHistory(updated.messages || []);
    await refreshChats();
    if (updated.title) chatTitleEl.textContent = updated.title;
    const statusResp = await apiFetch(projectQuery(`/api/chats/${chat.chat_id}/status`));
    const statusData = await statusResp.json();
    if (statusResp.ok && statusData.status?.investigation_run) {
      updateRunStatusPill(statusData.status.investigation_run);
    } else {
      updateRunStatusPill(null);
    }
    setStatus("就绪");
    toast("回复已就绪", "success");
  } catch (err) {
    toast(err.message || "等待回复失败", "error");
    setStatus("就绪");
  } finally {
    window.clearInterval(eventPollTimer);
    setBusy(false);
  }
}

function parseImageUrls(raw) {
  return raw
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter((item) => /^https?:\/\//i.test(item));
}

function currentImageUrls() {
  return pendingAttachments.map((item) => item.url).filter(Boolean);
}

let userStoppedRun = false;

async function sendMessage(text) {
  const message = text.trim();
  if (!message || busy || !currentChatId) return;
  if (!llmConfigured) {
    toast(
      isAdmin
        ? "请先在侧栏「LLM 配置」填写 API Key"
        : "LLM 未配置，请联系管理员",
      "error",
    );
    if (isAdmin) openLlmAdmin();
    return;
  }

  const imageUrls = currentImageUrls();
  let baselineCount = 0;
  try {
    const baselineResp = await apiFetch(projectQuery(`/api/chats/${currentChatId}/status`));
    const baselineData = await baselineResp.json();
    if (baselineResp.ok) {
      baselineCount = Number(baselineData.status?.message_count || 0);
    }
  } catch {
    baselineCount = 0;
  }

  setBusy(true);
  setStatus("正在思考…", "busy");
  addUserMessage(message, imageUrls);

  const { body, content, thinking } = createAssistantShell(true, { recordMode });
  content.classList.add("placeholder");
  content.textContent = "等待 Agent 响应…";
  thinking.addActivity("问题已提交，正在连接 Agent…", "system");

  chatAbortController = new AbortController();
  const { signal } = chatAbortController;
  let approvalPollTimer = null;

  let assistantText = "";
  let contentStarted = false;
  let renderScheduled = false;
  let latestConfidence = null;
  const chatActivities = [];

  const flushRender = () => {
    renderScheduled = false;
    const streaming = content.classList.contains("streaming");
    content.innerHTML = renderMarkdown(assistantText, { streaming });
    if (!streaming) bindCodeCopy(content);
    scrollToBottom();
  };

  const scheduleRender = () => {
    if (!renderScheduled) {
      renderScheduled = true;
      requestAnimationFrame(flushRender);
    }
  };

  const fail = (msg) => {
    thinking.finish(contentStarted);
    content.className = "msg-error";
    content.textContent = msg;
    setStatus("失败", "error");
  };

  try {
    const resp = await apiFetch(projectQuery("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        chat_id: currentChatId,
        conversation_id: agentConversationId,
        image_urls: imageUrls,
      }),
      signal,
    });

    if (!resp.ok) {
      const detail = await resp.text();
      fail(detail || "请求失败");
      return;
    }

    const headerConv = resp.headers.get("X-OpenHands-ServerConversation-ID");
    if (headerConv) {
      agentConversationId = headerConv;
      updateConversationMeta();
    }

    setStatus("生成回复中…", "busy");

    const activeChatIdForApproval = currentChatId;
    const approvalPollTimer = window.setInterval(() => {
      pollChatStatusForApproval(activeChatIdForApproval)
        .then((waiting) => {
          if (!waiting || currentChatId !== activeChatIdForApproval) return;
          window.clearInterval(approvalPollTimer);
          thinking.stop();
          if (!contentStarted) {
            content.classList.remove("placeholder");
            content.textContent = "工具调用待审批，请在下方输入框上方批准或拒绝。";
          }
          chatAbortController?.abort();
        })
        .catch(() => {});
    }, 2000);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      if (signal.aborted) {
        await reader.cancel();
        thinking.stop();
        if (userStoppedRun) {
          setStatus("已停止", "error");
        } else {
          setStatus("连接已断开，Agent 仍在后台分析…", "busy");
          const activeChatId = currentChatId;
          pollChatForReply(activeChatId, baselineCount, { maxAttempts: 90 })
            .then((result) => {
              if (!result?.message || currentChatId !== activeChatId) return;
              renderHistory(result.chat.messages || []);
              refreshChats().catch(() => {});
              setStatus("已从服务端恢复回复", "ready");
              toast("回复已就绪", "success");
            })
            .catch(() => {});
        }
        return;
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";

      for (const part of parts) {
        if (part.startsWith("event: ping")) {
          continue;
        }
        if (part.startsWith("event: activity")) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (line) {
            try {
              const meta = JSON.parse(line.slice(6));
              if (meta.activity) {
                const kind = meta.kind || "default";
                if (kind === "system" && meta.activity === "仍在分析…") {
                  continue;
                }
                chatActivities.push({ text: meta.activity, kind });
                thinking.addActivity(meta.activity, kind);
                if (kind === "error") setStatus("Agent 异常", "error");
                scrollToBottom();
                await new Promise((resolve) => requestAnimationFrame(resolve));
              }
            } catch { /* 忽略 */ }
          }
          continue;
        }
        if (part.startsWith("event: confidence")) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (line) {
            try {
              latestConfidence = JSON.parse(line.slice(6));
              attachConfidence(body, latestConfidence, chatActivities);
            } catch { /* 忽略 */ }
          }
          continue;
        }
        if (part.startsWith("event: meta")) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (line) {
            try {
              const meta = JSON.parse(line.slice(6));
              if (meta.conversation_id) {
                agentConversationId = meta.conversation_id;
                updateConversationMeta();
              }
              if (meta.run_id) {
                currentRunId = meta.run_id;
                thinking.setRunId(meta.run_id);
                updateRunStatusPill({ run_id: meta.run_id, status: "running" });
              }
            } catch { /* 忽略 */ }
          }
          continue;
        }
        const dataLine = part.split("\n").find((l) => l.startsWith("data: "));
        if (!dataLine) continue;
        const payload = dataLine.slice(6).trim();
        if (payload === "[DONE]") continue;
        try {
          const json = JSON.parse(payload);
          if (json.error) {
            fail(json.error);
            return;
          }
          const delta = json.choices?.[0]?.delta?.content;
          if (typeof delta === "string" && delta) {
            if (!contentStarted) {
              contentStarted = true;
              content.classList.remove("placeholder");
              content.classList.add("streaming");
              thinking.markReplyStarting();
              thinking.finish(true);
              setStatus("输出中…", "busy");
            }
            assistantText += delta;
            scheduleRender();
          }
        } catch { /* 忽略格式异常的分片 */ }
      }
    }

    if (renderScheduled) flushRender();
    content.classList.remove("streaming");

    if (!contentStarted) {
      thinking.finish(false);
      content.classList.remove("placeholder");
      content.textContent = "Agent 已完成运行，但未返回文本（可能仅执行了工具）。";
    } else {
      content.innerHTML = renderMarkdown(assistantText);
      bindCodeCopy(content);
      addToolbar(body, assistantText);
      if (latestConfidence) attachConfidence(body, latestConfidence, chatActivities);
    }

    setStatus("就绪");
    clearAttachments();
    await refreshChats();
    if (currentChatId) {
      const titleResp = await apiFetch(projectQuery(`/api/chats/${currentChatId}`));
      const titleData = await titleResp.json();
      if (titleResp.ok) chatTitleEl.textContent = titleData.chat.title || "新会话";
    }
  } catch (err) {
    if (err.name === "AbortError") {
      thinking.stop();
      if (userStoppedRun) {
        setStatus("已停止", "error");
      } else {
        setStatus("连接已断开，Agent 仍在后台分析…", "busy");
        const activeChatId = currentChatId;
        pollChatForReply(activeChatId, baselineCount, { maxAttempts: 90 })
          .then((result) => {
            if (!result?.message || currentChatId !== activeChatId) return;
            renderHistory(result.chat.messages || []);
            refreshChats().catch(() => {});
            setStatus("已从服务端恢复回复", "ready");
          })
          .catch(() => {});
      }
      return;
    }
    const recovered = await pollChatForReply(currentChatId, baselineCount);
    if (recovered?.message?.content) {
      thinking.finish(true);
      content.classList.remove("placeholder", "streaming");
      content.innerHTML = renderMarkdown(recovered.message.content);
      bindCodeCopy(content);
      addToolbar(body, recovered.message.content);
      if (Array.isArray(recovered.message.activities) && recovered.message.activities.length) {
        body.insertBefore(createStaticThinkingBlock(recovered.message.activities), content);
      }
      if (recovered.message.confidence) {
        attachConfidence(body, recovered.message.confidence, recovered.message.activities);
      }
      setStatus("已从服务端恢复回复", "ready");
      await refreshChats();
      return;
    }
    fail(err.message);
  } finally {
    if (approvalPollTimer !== null) {
      window.clearInterval(approvalPollTimer);
    }
    userStoppedRun = false;
    chatAbortController = null;
    setBusy(false);
    promptEl.focus();
  }
}

/* --------------------------------------------------------------------------
 * 数据加载
 * ------------------------------------------------------------------------ */

async function loadMe() {
  const resp = await apiFetch("/api/auth/me");
  const data = await resp.json();
  if (!resp.ok) throw new Error("获取用户失败");
  currentUser = data.user;
  isAdmin = Boolean(currentUser.is_admin);
  userLabel.textContent = currentUser.username;
  menuUserName.textContent = currentUser.username;
  userAvatar.textContent = currentUser.username[0].toUpperCase();
  if (adminBoardBtn) adminBoardBtn.classList.toggle("hidden", !isAdmin);
  if (adminProjectsBtn) adminProjectsBtn.classList.toggle("hidden", !isAdmin);
  if (adminLlmBtn) adminLlmBtn.classList.toggle("hidden", !isAdmin);
  document.querySelector(".user-role").textContent = isAdmin ? "管理员" : "分析工作台";
  if (syncKnowledgeBtn) syncKnowledgeBtn.classList.toggle("hidden", !isAdmin);
  if (reloadSkillsBtn) reloadSkillsBtn.classList.toggle("hidden", !isAdmin);
  syncAppState();
}

async function loadHealth() {
  try {
    const resp = await fetch("/api/health");
    if (!resp.ok) return;
    const data = await resp.json();
    llmConfigured = data.llm_configured !== false;
    modelLabelEl.textContent = data.model_label || data.model || "—";
    storageLabelEl.textContent = data.storage_backend || "—";
    const reposResp = await apiFetch(projectQuery("/api/knowledge/repos"));
    if (reposResp.ok) {
      const reposData = await reposResp.json();
      knowledgeLabelEl.textContent = Array.isArray(reposData.repos) && reposData.repos.length
        ? reposData.repos.map((r) => r.id).join(", ")
        : "未配置";
    }
  } catch { /* 忽略 */ }
}

/* --------------------------------------------------------------------------
 * 侧栏与菜单交互
 * ------------------------------------------------------------------------ */

function toggleMenu(btn, menu) {
  menu.classList.toggle("hidden");
  btn.setAttribute("aria-expanded", String(!menu.classList.contains("hidden")));
}

function closeAllMenus() {
  settingsMenu.classList.add("hidden");
  userMenu.classList.add("hidden");
}

document.addEventListener("click", (e) => {
  if (!settingsMenu.contains(e.target) && e.target !== settingsBtn && !settingsBtn.contains(e.target)) {
    settingsMenu.classList.add("hidden");
  }
  if (!userMenu.contains(e.target) && e.target !== userChipBtn && !userChipBtn.contains(e.target)) {
    userMenu.classList.add("hidden");
  }
});

settingsBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  userMenu.classList.add("hidden");
  toggleMenu(settingsBtn, settingsMenu);
});

userChipBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  settingsMenu.classList.add("hidden");
  toggleMenu(userChipBtn, userMenu);
});

function closeSidebarMobile() {
  sidebar.classList.remove("open");
  scrim.classList.add("hidden");
}

menuToggle.addEventListener("click", () => {
  sidebar.classList.add("open");
  scrim.classList.remove("hidden");
});

scrim.addEventListener("click", closeSidebarMobile);

searchInput.addEventListener("input", renderChatList);

const currentProjectIdRef = {
  get current() {
    return currentProjectId;
  },
  set current(value) {
    currentProjectId = value;
    App.currentProjectId = value;
  },
};

wireAdminToken({
  onRestoreChat: () => closeAdminView(),
});
wireAdminLlm({
  onClose: () => closeAdminView(),
  onHealth: loadHealth,
});
wireAdminProjects({
  onClose: () => closeAdminView(),
  loadProjects,
  loadHealth,
  currentProjectIdRef,
});

if (projectSelectEl) {
  projectSelectEl.addEventListener("change", async () => {
    try {
      await switchProject(projectSelectEl.value);
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

/* --------------------------------------------------------------------------
 * 侧栏与菜单动作
 * ------------------------------------------------------------------------ */

newChatBtn.addEventListener("click", async () => {
  try {
    await createChat();
  } catch (err) {
    toast(err.message, "error");
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch { /* 忽略 */ }
  localStorage.removeItem(TOKEN_KEY);
  window.location.replace("/");
});

syncKnowledgeBtn.addEventListener("click", async () => {
  settingsMenu.classList.add("hidden");
  setStatus("同步中…", "busy");
  try {
    const resp = await apiFetch(projectQuery("/api/knowledge/sync"), { method: "POST" });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "同步失败");
    knowledgeLabelEl.textContent = (data.synced || []).map((i) => i.repo_id).join(", ") || "已同步";
    setStatus("就绪");
    toast("知识库同步完成", "success");
  } catch (err) {
    setStatus("就绪", "error");
    toast(`同步失败: ${err.message}`, "error");
  }
});

reloadSkillsBtn.addEventListener("click", async () => {
  settingsMenu.classList.add("hidden");
  setStatus("重载中…", "busy");
  try {
    const resp = await apiFetch(projectQuery("/api/skills/reload"), { method: "POST" });
    if (!resp.ok) {
    const data = await resp.json();
      throw new Error(data.detail || "重载失败");
    }
    const data = await resp.json();
    setStatus("就绪");
    toast(`已重载 ${data.published?.length || 0} 个 Skill`, "success");
  } catch (err) {
    setStatus("就绪", "error");
    toast(`重载失败: ${err.message}`, "error");
  }
});

if (recordModeBtn) {
  recordModeBtn.addEventListener("click", () => {
    recordMode = !recordMode;
    localStorage.setItem(RECORD_MODE_KEY, recordMode ? "1" : "0");
    syncRecordModeUi();
    toast(recordMode ? "录屏模式已开启（Thinking 保持展开）" : "录屏模式已关闭", "info");
  });
}

ticketTemplateBtn.addEventListener("click", () => {
  settingsMenu.classList.add("hidden");
  if (!currentChatId) {
    toast("请先选择或新建对话", "info");
    return;
  }
  promptEl.value =
    "工单标题：服务异常\n\n现象：接口返回 500\n\n" +
    "请只读分析 workspace 中关联仓库的代码与日志，给出根因分析和修复建议。";
  autoResizePrompt();
  promptEl.focus();
});

/* --------------------------------------------------------------------------
 * 工具审批（输入框上方横幅）
 * ------------------------------------------------------------------------ */

if (runApprovalApproveBtn) {
  runApprovalApproveBtn.addEventListener("click", async () => {
    const runId = runApprovalBanner?.dataset.runId || currentRunId;
    if (!runId) return;
    try {
      await handleRunApprovalAction(runId, "approve");
    } catch {
      /* toast 已在 handleRunApprovalAction */
    }
  });
}

if (runApprovalRejectBtn) {
  runApprovalRejectBtn.addEventListener("click", async () => {
    const runId = runApprovalBanner?.dataset.runId || currentRunId;
    if (!runId) return;
    try {
      await handleRunApprovalAction(runId, "reject");
    } catch {
      /* toast 已在 handleRunApprovalAction */
    }
  });
}

/* --------------------------------------------------------------------------
 * 输入框
 * ------------------------------------------------------------------------ */

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = promptEl.value;
  promptEl.value = "";
  autoResizePrompt();
  sendMessage(text);
});

promptEl.addEventListener("input", autoResizePrompt);

promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

promptEl.addEventListener("paste", (e) => {
  handleComposerPaste(e).catch((err) => {
    toast(err.message || "粘贴截图失败", "error");
  });
});

if (attachBtnEl && imageFileInputEl) {
  attachBtnEl.addEventListener("click", () => {
    if (attachBtnEl.disabled) return;
    imageFileInputEl.click();
  });
  imageFileInputEl.addEventListener("change", () => {
    addImageFiles(imageFileInputEl.files).finally(() => {
      imageFileInputEl.value = "";
    });
  });
}

chatForm.addEventListener("dragover", (e) => {
  if (!Array.from(e.dataTransfer?.types || []).includes("Files")) return;
  e.preventDefault();
  chatForm.classList.add("drag-over");
});

chatForm.addEventListener("dragleave", () => {
  chatForm.classList.remove("drag-over");
});

chatForm.addEventListener("drop", (e) => {
  if (!Array.from(e.dataTransfer?.types || []).includes("Files")) return;
  e.preventDefault();
  chatForm.classList.remove("drag-over");
  addImageFiles(e.dataTransfer.files).catch((err) => {
    toast(err.message || "拖入截图失败", "error");
  });
});

stopBtn.addEventListener("click", async () => {
  userStoppedRun = true;
  if (chatAbortController) chatAbortController.abort();
  if (currentChatId || agentConversationId) {
    try {
      await apiFetch(projectQuery("/api/agent/cancel"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: agentConversationId,
          chat_id: currentChatId,
        }),
      });
    } catch {
      /* 忽略 cancel 失败 */
    }
  }
});

document.querySelectorAll(".hint-card").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!currentChatId) {
      try {
        await createChat();
      } catch (err) {
        toast(err.message, "error");
        return;
      }
    }
    promptEl.value = btn.dataset.hint || "";
    autoResizePrompt();
    promptEl.focus();
  });
});

/* 启动 */
(async function bootstrap() {
  try {
    await loadMe();
    await loadProjects();
    await loadHealth();
    await refreshChats();
    await restoreLastOpenChat();
    if (!currentChatId) {
      clearChatPanel();
    }
    if (isAdmin && !llmConfigured) {
      toast("请先配置 LLM API Key", "error");
      openLlmAdmin();
    }
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    window.location.replace("/");
  }
})();
