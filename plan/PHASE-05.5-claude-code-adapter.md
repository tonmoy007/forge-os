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

### CLI Surface (verified against claude 2.1.x — Slice 1.5)

```
claude -p <prompt> \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --allowedTools <tool1,tool2,...>
```

- `-p`: non-interactive, one-shot prompt
- `--output-format stream-json`: one JSON object per line on stdout
- **`--verbose`: REQUIRED** alongside `-p` + stream-json (the CLI errors without it)
- `--no-session-persistence`: stateless, no cross-run context leakage
- `--allowedTools`: enforce ALLOW policy (comma- *or* space-separated tool names)
- ~~`--max-turns`~~: **not a valid CLI flag in 2.1.x** — removed (the `-p` one-shot is naturally bounded)

### Stream-JSON Schema (verified — corrected in Slice 1.5)

> ⚠️ The original draft of this section guessed a `{"type":"text","content":...}` schema that does
> **not** match the real CLI. A captured gold sample lives at `tests/fixtures/claude_code/real_text_run.jsonl`.

Each line is an envelope:
```
{"type": "system",    "subtype": "init", ...}                       session metadata
{"type": "assistant", "message": {"role":"assistant", "content": [   one assistant turn
    {"type": "text", "text": "..."},
    {"type": "tool_use", "id": "...", "name": "Read", "input": {...}}]}}
{"type": "user",      "message": {"content": [                        tool results fed back
    {"type": "tool_result", "tool_use_id": "...", "content": "..."}]}}
{"type": "result",    "subtype": "success"|"error_*", "is_error": false,
    "result": "<final text>", "usage": {...}, "total_cost_usd": 0.0}
```

Text is at `message.content[].text` (NOT a top-level `content`). The final answer is the `result`
line's `result` field. **Token usage and cost ARE present** in the `result` line's `usage` /
`total_cost_usd` (the old note claiming tokens needed `--output-format json` was wrong). Other line
types (`rate_limit_event`, `system` hook subtypes) are recorded verbatim but carry no adapter payload.

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

**Status:** Complete (2026-06-09). Tests: `tests/test_adapters_claude_code_hooks.py` + extended
`tests/test_adapters_claude_code.py`. Full suite 395 passing (host + clean `python:3.12-slim` Docker,
latest deps), ruff clean, compileall clean.

Hooks in `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "<caller-supplied>"}]}],
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "<caller-supplied>"}]}]
  }
}
```

`ClaudeSettingsHookWriter` (`adapters/claude_code/hooks.py`) installs a hook config before spawn and
tears it down after (even on failure), restoring the project's prior `.claude/settings.json` byte-for-byte
(or removing a file/dir it created). The hook **command is caller-injected** — the adapter does not
hardcode a `forge hook` subcommand, because that CLI does not exist yet; wiring it follows when it does.
The adapter enables hooks only when constructed with `hook_command=...`.

Every stream-json line is appended to the event store under a per-spawn `run_id` stream. The recorded
event types (PascalCase, matching the EventStore convention; defined as constants in `adapter.py`):

| Event type | When | Payload |
|---|---|---|
| `AdapterSpawnStarted` | before subprocess | persona_id, role, stage_id, prompt, context, granted_tools, claude_tools, max_turns |
| `AdapterStreamEvent` | per stream-json line | `{type, raw}` (the full parsed line) |
| `AdapterSpawnCompleted` | on success | status, returncode, tool_use_count, text_length, metadata |
| `AdapterSpawnFailed` | on `ClaudeCodeSpawnError` | returncode, error |

`run_id` is exposed on `AgentHandle.metadata["run_id"]` so Slice 3 replay can reconstruct the handle.

**Determinism implementation note (batch vs. streaming).** The runner keeps `subprocess.run` (batch) and
invokes the `on_event` callback per parsed line *after* the subprocess returns, rather than streaming each
line byte-by-byte during execution. The ADR-005 / FR-ES-001 requirement — *the full stream-json transcript
is captured to the immutable event store, and replay reconstructs the handle without re-invoking the kernel*
— is fully met either way: for a completed run the recorded event set is identical. True byte-by-byte
streaming would add a stderr-drain thread plus a SQLite cross-thread hazard for negligible benefit on a
one-shot `claude -p` call; the only difference is partial-capture on mid-run crash, and a crash already
records `AdapterSpawnFailed` with stderr. This is a deliberate, documented tradeoff — not a shortcut.

---

## Slice 3 — Replay

**Status:** Complete (2026-06-09). `adapters/claude_code/replay.py` + `tests/test_adapters_claude_code_replay.py`.
Full suite 417 passing (host + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean.

`ClaudeCodeAdapter.replay_session(run_id)` (delegating to `replay.replay_session(event_store, run_id)`) reads
the recorded events for `run_id` and reconstructs the `AgentHandle` **without touching the subprocess**. This
satisfies ADR-005 / FR-ES-003 determinism: the same run ID produces the same handle every time.

**How it reconstructs (projection, not snapshot):**
- `AdapterSpawnStarted` → `provider`, `persona_id`, `stage_id`.
- the `AdapterStreamEvent` lines → a rebuilt `RunResult`, from which `outputs` are re-derived via the shared
  `extract_text_outputs` (the same projection live spawn uses — single source of truth).
- `AdapterSpawnCompleted` → `status`, `handle_id` (the one non-derivable field, recorded in Slice 2's completed
  event for this purpose), and `metadata` (read verbatim — it *is* the recorded projection).
- The reconstructed handle is `== ` the originally returned handle (Pydantic value equality).

**Failed / incomplete / missing runs** raise `ReplayError`: a failed run produced no handle originally (the spawn
raised), an incomplete run has no terminal event, and a missing run has no recorded stream.

**Cycle avoidance:** `replay.py` imports the event-type constants + `extract_text_outputs` from `adapter.py` at
module level; `adapter.py` imports `replay_session` **lazily** inside the method, so module-load is acyclic.

---

## Slice 4 — Adapter selection + `forge adapter status`

**Status:** Complete (2026-06-09, P055.11-12). 439 tests (host + clean `python:3.12-slim` Docker +
GitHub CI), ruff clean, compileall clean.

> The original draft said "`GateUseCases.run_gate()` picks DummyAdapter… fall back to DummyAdapter." That
> was stale: the real selection seam is `create_adapter_from_config(project_root, config)`
> (`adapters/registry.py`), called from `agents/executor.py::run_stage_agent`. Selection is **config-driven**
> via `config.default_adapter`, not auto-detection.

**P055.11 — make `claude_code` actually selectable.** `_claude_code_factory` was broken: it passed `model=`
(which `ClaudeCodeAdapter.__init__` doesn't accept) and had no binary check, so `default_adapter: claude_code`
would crash. Now it does `shutil.which(claude_bin)` (raising `AdapterRegistryError` with an install hint if
absent, like `_codex_factory`) and passes `claude_bin` + optional `model`. Model support was threaded end to
end: `ClaudeCodeAdapter(model=None)` → `run_claude(model=…)` → `--model <m>` only when configured.

**Selection policy (deviation from the stale "fallback" prose).** We keep config-driven selection and **fail
loud** when the configured adapter is unavailable, rather than silently falling back to `DummyAdapter` —
silent fallback would produce fake artifacts while the user believes a real kernel ran, violating the
project's fail-loud rule. The default `default_adapter` is already `dummy`, so a fresh clone works without
`claude`; you only get `claude_code` by explicitly configuring it, and a missing binary is then a clear error.

**P055.12 — `forge adapter status`.** `use_cases/adapters.py::AdapterUseCases.status()` probes each adapter
(constructs it via the registry, catching failures) and reports `enabled / default / available / reason /
capabilities`; *available* = constructs without raising and isn't a placeholder. The CLI command renders it,
so a user can see at a glance whether `claude_code` is selectable right now (binary on PATH? dep installed?).

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
