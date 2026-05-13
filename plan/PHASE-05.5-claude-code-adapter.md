# Phase 05.5 — ClaudeCodeAdapter (Kernel-First, D5=B)

**Status:** In Progress  
**Priority:** P0 — must land before Phase 10, license flip, or open-source outreach  
**ADRs honoured:** ADR-001 (local-first), ADR-002 (no cloud dependency for core), ADR-003 (KernelAdapter boundary), ADR-005 (determinism boundary)  
**Predecessor:** Phase 05 (adapters/agents interface)  
**Successor:** Phase 10 (daemon, dreamer, lazy context)

---

## Motivation

Phase 05 shipped the `KernelAdapter` protocol and `DummyAdapter`. Forge OS currently has **no real kernel** — every agent invocation produces deterministic dummy artifacts. A real product needs at least one real kernel.

`ClaudeCodeAdapter` is the right first adapter because:
- The developer uses Claude Code daily (honest dogfood)
- Claude Code exposes a stable, well-documented subprocess CLI surface
- The interface fits the `KernelAdapter` protocol exactly
- It demonstrates the full determinism/traceability/replay requirement (ADR-005)

---

## Design Principles

### Determinism Boundary (ADR-005 §3.33)

LLM calls are non-deterministic. The adapter's job is to **bound non-determinism** at the subprocess boundary:

1. Record `spawn` parameters (persona, context, tool list) to the event store before subprocess starts.
2. Stream and record every `stream-json` line to the event store as it arrives.
3. On completion, record exit code + final AgentHandle to the event store.
4. **Replay** = read from event store, do NOT re-invoke the subprocess.

This means `ClaudeCodeAdapter` is a thin adapter over a `ClaudeCodeRunner` that streams and records.

### CLI Surface

```
claude -p <prompt> \
  --output-format stream-json \
  --no-session-persistence \
  --allowedTools <tool1,tool2,...> \
  --max-turns <n>
```

- `-p`: non-interactive, one-shot prompt
- `--output-format stream-json`: one JSON object per line on stdout
- `--no-session-persistence`: stateless, no cross-run context leakage
- `--allowedTools`: enforce ALLOW policy (deny everything not listed)
- `--max-turns`: safety cap on recursive agent loops

### Stream-JSON Schema

Each line is one of:
```
{"type": "text",        "content": "..."}
{"type": "tool_use",    "id": "...", "name": "Read", "input": {...}}
{"type": "tool_result", "tool_use_id": "...", "content": "..."}
{"type": "message",     "role": "assistant", "content": [...]}
{"type": "error",       "error": {"type": "...", "message": "..."}}
```

Token counts appear only in `--output-format json` final output, not in stream-json lines.

---

## Deliverables Table

| ID | Slice | Deliverable | File |
|----|-------|-------------|------|
| P055.01 | 1 | `tool_map.py` — abstract tool ID → Claude Code tool name | `adapters/claude_code/tool_map.py` |
| P055.02 | 1 | `runner.py` — subprocess + stream-json parser | `adapters/claude_code/runner.py` |
| P055.03 | 1 | `ClaudeCodeAdapter` skeleton (spawn_agent, get_default_tools, supports) | `adapters/claude_code/adapter.py` |
| P055.04 | 1 | `__init__.py` — package exports | `adapters/claude_code/__init__.py` |
| P055.05 | 1 | Tests: mocked subprocess, fixture stream-json | `tests/test_adapters_claude_code.py` |
| P055.06 | 2 | Hook capture: pre/post tool-use hooks via `.claude/settings.json` | `adapters/claude_code/hooks.py` |
| P055.07 | 2 | Event-store integration: record stream-json events on arrival | `adapters/claude_code/adapter.py` (extend) |
| P055.08 | 2 | Tests: hook round-trip, event-store write verification | `tests/test_adapters_claude_code.py` (extend) |
| P055.09 | 3 | Replay: `ClaudeCodeAdapter.replay_session(run_id)` from event store | `adapters/claude_code/replay.py` |
| P055.10 | 3 | Tests: replay from fixture event store, no subprocess invoked | `tests/test_adapters_claude_code_replay.py` |
| P055.11 | 4 | Gate integration: `forge run` picks ClaudeCodeAdapter when available | `use_cases/gates.py` (extend adapter selection) |
| P055.12 | 4 | `forge adapter status` command | `cli/commands/adapter.py` |
| P055.13 | 5 | Security: `SecurityEnforcer` check before subprocess spawn | `adapters/claude_code/adapter.py` (extend) |
| P055.14 | 5 | Tests: deny policy blocks spawn, audit entry written | `tests/test_adapters_claude_code.py` (extend) |
| P055.15 | 6 | `forge init --adapter claude-code` bootstrap + `--permission-mode` flag | `cli/commands/init.py` (extend), `adapters/claude_code/adapter.py` |

---

## Slice 1 — Subprocess Wrapper + Adapter Skeleton

**Acceptance criteria:**
1. `ClaudeCodeAdapter("dummy-root")` instantiates without network call.
2. `get_default_tools()` returns at least `["read_file", "write_file", "edit_file", "bash", "list_files"]`.
3. `supports("stream")` → `True`; `supports("acp")` → `False`.
4. `spawn_agent(persona, context, tools)` with a mocked subprocess returning fixture stream-json returns a completed `AgentHandle` with `provider="claude-code"`.
5. `spawn_agent` raises `ClaudeCodeSpawnError` when subprocess exits non-zero.
6. All tests pass, ruff clean, compileall clean.

**Not in Slice 1:**
- Real subprocess invocation (no `claude` binary required — tests are mocked)
- Event-store write (Slice 2)
- Hook capture (Slice 2)
- Replay (Slice 3)

---

## Slice 2 — Hook Capture + Event Store

Hooks in `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "forge hook pre-tool"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "forge hook post-tool"}]}]
  }
}
```

The adapter writes a hook config before spawn and tears it down after.  
Every stream-json event is appended to the event store as type `ADAPTER_STREAM`.

---

## Slice 3 — Replay

`replay_session(run_id: str)` reads events from the event store and reconstructs the `AgentHandle` without touching the subprocess. This satisfies ADR-005 determinism: the same run ID produces the same handle every time.

---

## Slice 4 — Gate Integration

`GateUseCases.run_gate()` currently picks DummyAdapter. After Slice 4, it checks:
1. Is `claude` binary on `PATH`?
2. Is adapter configured in `config.yaml`?
3. If yes to both, use `ClaudeCodeAdapter`. Otherwise fall back to `DummyAdapter`.

---

## Slice 5 — Security Integration

Before `runner.py` spawns the subprocess, call `SecurityEnforcer.validate_action(actor, "execute_command", capability="shell")`. If `DENIED`, raise `ClaudeCodeSpawnError`. The audit log records the decision.

---

## Slice 6 — Init Bootstrap

`forge init --adapter claude-code` writes `adapter: claude-code` to `config.yaml` and verifies the `claude` binary is on PATH with a version check.

---

## Exit Checklist

Before advancing to Phase 10:
- [ ] Slices 1-3 complete (subprocess, hooks, replay)
- [ ] `ruff check src tests` → 0 errors
- [ ] `compileall src tests` → clean
- [ ] 4 PLAYBOOK grep gates pass
- [ ] `forge run srs` with `ClaudeCodeAdapter` produces a real SRS artifact
- [ ] `forge adapter status` shows adapter info and capabilities
- [ ] `CURRENT_PHASE.md` updated to Phase 10

---

## Kill Criterion

If after 14 days `ClaudeCodeAdapter` cannot complete a single real `forge run srs` end-to-end (persona → subprocess → artifact → contract pass), stop and re-evaluate the adapter boundary design before continuing.
