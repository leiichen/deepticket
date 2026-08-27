#!/usr/bin/env python3
"""端到端自测：require_approval 前台展示 + 拒绝/批准行为。"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8600"
PROJECT = "default"
PROMPT = "请使用 MCP 工具 demo_exec_command 执行命令 ls -la，并告诉我返回结果。"
POLL_SEC = 2
MAX_WAIT_SEC = 180


def http_json(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def login() -> str:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps({"username": "admin", "password": "admin"}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["token"]


def create_chat(token: str, title: str) -> str:
    status, data = http_json(
        "POST",
        f"/api/chats?project_id={PROJECT}",
        token,
        {"title": title},
    )
    if status != 200:
        raise RuntimeError(f"create chat failed: {status} {data}")
    return data["chat"]["chat_id"]


def chat_status(token: str, chat_id: str) -> dict:
    status, data = http_json(
        "GET",
        f"/api/chats/{chat_id}/status?project_id={PROJECT}",
        token,
    )
    if status != 200:
        raise RuntimeError(f"status failed: {status} {data}")
    return data["status"]


def run_detail(token: str, run_id: str) -> dict:
    status, data = http_json(
        "GET",
        f"/api/runs/{run_id}?project_id={PROJECT}",
        token,
    )
    if status != 200:
        raise RuntimeError(f"run detail failed: {status} {data}")
    return data


def post_approval(token: str, run_id: str, action: str) -> None:
    status, data = http_json(
        "POST",
        f"/api/runs/{run_id}/{action}?project_id={PROJECT}",
        token,
        {"reason": f"selftest {action}"},
    )
    if status != 200:
        raise RuntimeError(f"{action} failed: {status} {data}")


def stream_chat(token: str, chat_id: str, message: str) -> None:
    url = f"{BASE}/api/chat?project_id={PROJECT}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"message": message, "chat_id": chat_id}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=MAX_WAIT_SEC) as resp:
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break


def start_chat(token: str, chat_id: str, message: str) -> threading.Thread:
    thread = threading.Thread(
        target=stream_chat,
        args=(token, chat_id, message),
        daemon=True,
    )
    thread.start()
    return thread


def wait_for_waiting_approval(token: str, chat_id: str) -> dict:
    deadline = time.time() + MAX_WAIT_SEC
    while time.time() < deadline:
        status = chat_status(token, chat_id)
        inv = status.get("investigation_run") or {}
        if inv.get("status") == "waiting_approval":
            pending = status.get("pending_approval")
            if not pending:
                pending = run_detail(token, inv["run_id"]).get("pending_approval")
            if pending:
                status = dict(status)
                status["pending_approval"] = pending
                return status
        if status.get("agent_run_status") == "idle" and inv.get("status") in {
            "completed",
            "blocked",
            "failed",
        }:
            raise RuntimeError(
                f"run ended before approval: inv={inv}, agent={status.get('agent_run_status')}"
            )
        time.sleep(POLL_SEC)
    raise TimeoutError(f"timeout waiting approval for chat {chat_id}")


def wait_for_terminal(token: str, chat_id: str, *, expect: set[str]) -> dict:
    deadline = time.time() + MAX_WAIT_SEC
    while time.time() < deadline:
        status = chat_status(token, chat_id)
        inv = status.get("investigation_run") or {}
        run_status = inv.get("status")
        if not run_status and status.get("recent_runs"):
            run_status = status["recent_runs"][0].get("status")
        if run_status in expect:
            return status
        if status.get("agent_run_status") == "idle" and run_status in expect:
            return status
        time.sleep(POLL_SEC)
    raise TimeoutError(f"timeout waiting {expect}, last={chat_status(token, chat_id)}")


def assert_true(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  OK  {label}")
    else:
        print(f" FAIL {label} {detail}")
        raise AssertionError(f"{label}: {detail}")


def test_reject_flow(token: str) -> None:
    print("\n== 拒绝流程 ==")
    chat_id = create_chat(token, "selftest-reject")
    print(f"chat_id={chat_id}")
    worker = start_chat(token, chat_id, PROMPT)
    status = wait_for_waiting_approval(token, chat_id)
    inv = status["investigation_run"]
    pending = status["pending_approval"]
    assert_true("status 含 pending_approval", pending is not None)
    assert_true("工具名正确", pending.get("tool_name") == "demo_exec_command")
    assert_true("Run 为 waiting_approval", inv.get("status") == "waiting_approval")
    run_id = inv["run_id"]
    detail = run_detail(token, run_id)
    assert_true("runs API pending", detail.get("pending_approval") is not None)
    post_approval(token, run_id, "reject")
    worker.join(timeout=5)
    final = wait_for_terminal(token, chat_id, expect={"blocked"})
    run_status = (final.get("investigation_run") or final.get("recent_runs", [{}])[0]).get(
        "status"
    )
    assert_true("拒绝后 Run=blocked", run_status == "blocked")
    assert_true("拒绝后 chat idle", final.get("agent_run_status") == "idle")


def test_approve_flow(token: str) -> None:
    print("\n== 批准流程 ==")
    chat_id = create_chat(token, "selftest-approve")
    print(f"chat_id={chat_id}")
    worker = start_chat(token, chat_id, PROMPT)
    status = wait_for_waiting_approval(token, chat_id)
    inv = status["investigation_run"]
    run_id = inv["run_id"]
    assert_true("待审批工具 demo_exec_command", status["pending_approval"]["tool_name"] == "demo_exec_command")
    post_approval(token, run_id, "approve")
    deadline = time.time() + MAX_WAIT_SEC
    saw_running = False
    while time.time() < deadline:
        cur = chat_status(token, chat_id)
        inv = cur.get("investigation_run") or {}
        inv_status = inv.get("status")
        if not inv_status and cur.get("recent_runs"):
            inv_status = cur["recent_runs"][0].get("status")
        agent_status = cur.get("agent_run_status")
        if inv_status == "running":
            saw_running = True
        if inv_status == "completed" and agent_status == "idle":
            break
        if inv_status in {"failed", "blocked"}:
            raise RuntimeError(f"approve resume failed: {cur}")
        time.sleep(POLL_SEC)
    else:
        raise TimeoutError("approve resume did not complete")
    worker.join(timeout=5)
    final = chat_status(token, chat_id)
    final_run = final.get("investigation_run") or (final.get("recent_runs") or [{}])[0]
    assert_true("批准后 Run=completed", final_run.get("status") == "completed")
    assert_true("批准后 chat idle", final.get("agent_run_status") == "idle")
    status_code, chat_data = http_json(
        "GET",
        f"/api/chats/{chat_id}?project_id={PROJECT}",
        token,
    )
    assert_true("有 assistant 回复", status_code == 200)
    messages = chat_data.get("chat", {}).get("messages", [])
    assert_true("assistant 消息非空", any(m.get("role") == "assistant" and m.get("content") for m in messages))


def main() -> int:
    print("DeepTicket 审批流自测")
    token = login()
    test_reject_flow(token)
    test_approve_flow(token)
    print("\n全部自测通过。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n自测失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
