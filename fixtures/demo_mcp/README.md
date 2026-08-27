# deepticket-demo MCP

Side-effect-free stdio MCP for governance and Run Timeline testing.

Tool names use underscores (`demo_lookup`) because OpenAI/LiteLLM requires `^[a-zA-Z0-9_-]+$`.

## Run

From repository root:

```bash
.venv/bin/python -m fixtures.demo_mcp
```

## Tools

| Tool | Behavior |
|------|----------|
| `demo_lookup` | Fixed JSON for keys like `order-123` |
| `demo_read_config` | Fixed config snapshot |
| `demo_echo` | Echo parameters (varies per call) |
| `demo_delete_resource` | Always `dry_run: true` |
| `demo_exec_command` | Returns `would_run`, never executes |

Set `DEMO_EXTRA_TOOL=1` to also expose `demo_unknown_action`.

## Project MCP config (Admin → 项目配置 → MCP)

```yaml
deepticket-demo:
  transport: stdio
  command: /ABS/PATH/deepticket/.venv/bin/python
  args: ["-m", "fixtures.demo_mcp"]
  enabled: true
```

Use the **repository root** as the Agent Server working directory (default local setup), or pass an absolute path to `python` and ensure `fixtures` is importable (repo root on `PYTHONPATH`).

## Policy examples (future P0)

```yaml
tool_governance:
  tools:
    demo_delete_resource:
      decision: deny
    demo_exec_command:
      decision: require_approval
```
