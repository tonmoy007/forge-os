# Current Forge OS Phase

> ⛔ **STRATEGIC PAUSE — 2026-05-13.** Phase 10 implementation is **paused** pending the strategic decisions in `/STATUS.md` (D4-D8: name three real users, pick fork A/B/C, set kill criteria). Do not resume tactical phase work until D5 resolves.
>
> **Read order:** `/STATUS.md` → `/CLAUDE.md` → this file → the current phase file.
>
> **Session Continuity:** If this session is interrupted, run `git log --oneline -5 && git diff HEAD && cat plan/RESUME.md 2>/dev/null || echo "No RESUME.md"` before continuing.
> Last validated: 371 tests passed (host `.venv` + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean — 2026-06-08.

## Active Work: Phase 05.5 (kernel-first, D5=B)

Per D5=B (open-source kernel-first sequencing), tactical work resumed on the **kernel adapter layer** ahead of Phase 10. Landed (2026-06-08, PRs #1 + #2):

- `kernel/types.py` — canonical adapter contract (EventKind, NormalizedEvent, ToolUseProposal, ToolResult, AgentPersona, KernelCapabilities, IKernelAdapter)
- 5 new adapters: `human`, `claude_raw`, `claude_sdk`, `codex`, `opencode` (all implementing `IKernelAdapter`, async-generator + proposal-boundary)
- `adapters/bridge.py` — `AsyncToSyncBridge` (IKernelAdapter → sync `KernelAdapter` Protocol)
- `adapters/registry.py` — all 6 adapters registered with optional-dep guards
- `harness/comparison_harness.py` — multi-kernel benchmark harness
- Full test coverage: every adapter module now has a test file (rule #5). 371 tests total.
- L006 captured: validate in Docker with latest deps before claiming green.

**ClaudeCodeAdapter Slice 2 — landed 2026-06-09 (P055.06-08):** hook lifecycle (`adapters/claude_code/hooks.py::ClaudeSettingsHookWriter`) + event-store recording (`AdapterSpawnStarted` → N×`AdapterStreamEvent` → `AdapterSpawnCompleted`/`AdapterSpawnFailed` under a per-spawn `run_id`; `run_id` exposed on `AgentHandle.metadata`). 395 tests (host + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean.

**Task-ID collision resolved:** the multi-adapter expansion commit (`deb4bec`) was loosely labelled "P055.06-12"; that label is informal. The phase-doc deliverables table is the single source of truth — P055.06-08 are Slice 2 (just landed), P055.09-15 remain ClaudeCodeAdapter Slices 3-6.

**ClaudeCodeAdapter Slice 1.5 — real-contract reconciliation, 2026-06-09:** a de-risk check against the real `claude` v2.1.169 found Slices 1–3 were built on a *fabricated* stream-json schema (the phase doc guessed `{"type":"text",...}`; reality is `system`/`assistant`/`user`/`result` envelopes) plus wrong flags (`--max-turns` doesn't exist; `--verbose` is required). Rewrote `runner.py` (flags + parser), dropped `max_turns`, now record real token usage/cost, committed a gold capture (`tests/fixtures/claude_code/real_text_run.jsonl`) with a test that parses it. Captured as **L007**. 427 tests, ruff/compileall clean.

**ClaudeCodeAdapter Slice 3 — landed 2026-06-09 (P055.09-10):** `adapters/claude_code/replay.py` — `ClaudeCodeAdapter.replay_session(run_id)` reconstructs the `AgentHandle` by re-projecting the recorded `AdapterSpawnStarted`/`AdapterStreamEvent`/`AdapterSpawnCompleted` stream **without** invoking the subprocess (FR-ES-003 / FR-ES-004 / ADR-005); `ReplayError` for missing/incomplete/failed runs. Slice 2's completed event now records `handle_id` so replay restores the exact handle. 417 tests (host + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean.

**Deferred (next slices, per `plan/PHASE-05.5-claude-code-adapter.md`):** Slice 4 (gate integration + `forge adapter status`, P055.11-12), Slice 5 (security enforcer pre-spawn, P055.13-14), Slice 6 (`forge init --adapter claude-code`, P055.15).

## Next Phase (gated)

- Phase: 10
- File: `plan/PHASE-10-daemon-dreamer-lazy-context.md`
- Status: **paused (strategic review)** — was: in-progress

## Current Objective

Add optional always-on behavior: background daemon, Observer scheduling, Dreamer daily/weekly maintenance, lesson decay, lazy context loading, and continuous ACP agent health monitoring via the session management foundation from Phase 08.

## Last Completed Phase

- Phase: 09
- File: `plan/PHASE-09-health-global-skills.md`
- Status: complete

## Discipline & Clean Code Enforcement (Phase 08+)

Before implementing any task, run:
```bash
git log --oneline -5
git diff HEAD
git status
cat plan/RESUME.md 2>/dev/null || echo "No resume needed"
```

All Phase 08+ implementations MUST follow:

| Rule | How to Verify |
|------|--------------|
| **CLI never imports domain directly** | `grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/` — **zero matches required** |
| **No upward imports from domain** | `grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/kernel/` — **zero matches required** |
| **Schemas are pure data** | `grep -rn "from forge_os" src/forge_os/schemas/ --include="*.py"` — **only stdlib/pydantic imports allowed** |
| **Every use case has tests** | `ls tests/test_use_cases_*.py` — must exist for each `src/forge_os/use_cases/*.py` |

Last validation commands:

- `.venv/bin/python -m pytest` — 67 passed.
- `.venv/bin/python -m ruff check src tests` — passed.
- `.venv/bin/python -m compileall src tests` — passed.

Expected test count after Phase 08: 120+ passed.

## Resolved Decisions

1. Runtime: Python 3.11+.
2. Package import name: `forge_os`.
3. Preferred CLI command: `forge`.
4. Development package manager preference: `uv`, while preserving standard `pip` compatibility.
5. Distribution: local Python package first, `pipx` when ready, standalone binary later.
6. Adapter priority:
   1. `DummyAdapter`
   2. `ClaudeCodeAdapter`
   3. `CodexAdapter`
   4. `OpenClawAdapter`
   5. `OpenCodeAdapter`
   6. `LocalLLMAdapter`
   7. `HumanAdapter`
7. OpenClawAdapter architecture: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
8. Core state ownership: Forge OS core is the sole writer of canonical state.
9. Open formats: YAML, JSON, JSON Lines, Markdown, and GraphML.
10. Security baseline: least privilege, human approval for high-risk/destructive actions, explicit timeouts for executable checks.
11. ACP Protocol: JSON-RPC 2.0 over newline-delimited JSON on stdio.
12. ACP Registry: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
13. ACP session features (list, resume, close) are stabilized as of April 2026.
14. ACP agents must be registered in the official ACP Registry at `github.com/agentclientprotocol/registry`.
15. ACP integration is additive — existing LiteLLMAdapter behavior is preserved.
16. ACP agent installation supports: binary archives, npx packages, and uvx packages per manifest.
17. ACP agents spawned by Forge OS must respect SecurityEnforcer policies.
18. Phase 01 CLI scaffold is complete with `forge init`, `forge status`, `forge config show`, `forge config validate`, and `forge explain`.
19. Phase 02 state machine is complete with `forge stage list/start/complete/advance/override`, atomic writes, transition validation, state markdown sync, and transition event logging.
20. Phase 03 events/hooks are complete with normalized lifecycle events, in-process event bus, hook registry, hook timeout/failure isolation, and `forge events list/tail`.
21. Phase 04 gates MVP is complete with file/pattern gates, severity handling, gate reports, `forge gate list/check/report`, gate events, persisted latest results, and stage advancement enforcement.
22. Phase 05 adapters/agents are complete with KernelAdapter interface, adapter registry/config placeholders, DummyAdapter, 12 stage personas, 4 cross-stage personas, output contracts, agent execution logs, `forge adapter list`, `forge agent list/contracts/run`, and optional `forge stage start --spawn-agent`.
23. Phase 06 memory/lessons are complete with YAML lesson store, reflection files, lesson add/list/approve/deprecate CLI, reflection list/show CLI, stage-completion reflection capture, pending lesson extraction queue, and approved high-confidence lesson injection into agent context.
24. Phase 07 ADG/context is complete with artifact registry, JSON ADG persistence, stale downstream propagation, deterministic spread-activation context pruning, context selection audit logs, artifact/context CLI commands, stale artifact display in `forge status`, and pruned context integration for agent spawns.
25. **Phase 08 CLI refactoring complete** — all Phase 08+ commands moved to `src/forge_os/cli/commands/` sub-modules (`backtrack.py`, `security.py`, `health.py`, `acp.py`). `main.py` slimmed from 1240→895 lines. Separation of concerns enforced for all future commands.

## Blocking Questions

None currently.

## Phase 09 Task Summary

### Health Checks
| ID | Task | Status |
|---|---|---|
| P09.01 | Implement `forge health check` | 🔄 |
| P09.02 | Add hook unit test harness | 🔄 |
| P09.03 | Add gate simulation fixtures | 🔄 |
| P09.04 | Knowledge integrity scanner | 🔄 |
| P09.05 | Token budget report | 🔄 |

### Global Memory
| ID | Task | Status |
|---|---|---|
| P09.06 | Global memory directory under `~/.forge/` | 🔄 |
| P09.07 | Global lesson promotion with approval | 🔄 |
| P09.08 | Project profiles memory | 🔄 |
| P09.09 | Pattern tracker | 🔄 |

### Skill Mining
| ID | Task | Status |
|---|---|---|
| P09.10 | Skill proposal command | 🔄 |
| P09.11 | Skill approval workflow | 🔄 |
| P09.12 | Skill install/use commands | 🔄 |

### ACP Agent Health
| ID | Task | Status |
|---|---|---|
| P09.13 | ACP agent health checks using session/list | 🔄 |
| P09.14 | Agent restart/recovery logic | 🔄 |
| P09.15 | Session health monitoring | 🔄 |

### Phase 09 Validation
| Item | Target |
|---|---|
| Tests pass | TBD (186 baseline) |
| Ruff lint | clean |
| Compileall | clean |

## Notes For The Next Implementer

Read:

1. `BUILD_SPEC.md`
2. `plan/ORCHESTRATOR.md`
3. `plan/PHASE-08.5-async-cocoindex.md` — current phase plan
4. `plan/PHASE-08-backtrack-security.md` — completed phase for reference
5. `plan/PHASE-07-adg-context.md`
6. `plan/PHASE-05-adapters-agents.md`
7. `plan/v4/KERNEL_UPDATED_PLAN.md` — async research, ACP registry details
8. `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — CocoIndex evaluation details
9. `plan/KERNEL_ADAPTER_INTERFACE.md`
10. `plan/ADAPTER_ROADMAP.md`
11. `ARCHITECTURE.md`
12. `SCHEMAS.md`
13. Existing source under `src/forge_os/`
14. Existing tests under `tests/`

### Phase 08.5 Completed Deliverables

| Workstream | Deliverable | Status |
|---|---|---|
| **A: Async Migration** | AsyncKernelAdapter protocol, AsyncDummyAdapter, async executor, HTTP client | ✅ |
| **B: Incremental Cache** | Lightweight mtime+content cache replacing CocoIndex (zero deps) | ✅ |
| **C: Event Store** | SQLite append-only log, dual-write, replay, snapshots, Phase 08 events | ✅ |

### Deferred Items

- LiteLLMAdapter ACP integration + fallback chain — deferred to async migration cleanup
- Full event-sourced state migration — deferred to later phases
- Task ID numbering divergence: CURRENT_PHASE.md renumbered P08.5.x for brevity

### Clean Code Rules (Continuing)

All new Phase 09+ commands MUST live in their own file under `src/forge_os/cli/commands/<domain>.py`.
Each file exposes a Typer sub-app. Register with `app.add_typer()` in `main.py`.
Business logic belongs in `use_cases/`, not in CLI command files.

### Directory Structure (Phase 09)

```
src/forge_os/
├── adapters/
│   ├── async_base.py        # AsyncKernelAdapter protocol (Phase 08.5)
│   ├── async_dummy.py       # AsyncDummyAdapter (Phase 08.5)
│   ├── base.py              # Sync KernelAdapter protocol (preserved)
│   └── dummy.py             # Sync DummyAdapter (preserved)
├── agents/
│   └── executor.py          # run_stage_agent_async added (Phase 08.5)
├── context/
│   ├── pruner.py            # mtime cache added (Phase 08.5)
├── events/
│   ├── store.py             # Event Store for dual-write (Phase 08.5)
│   └── model.py             # Phase 08 event types registered
├── kernel/
│   ├── acp_client.py        # Phase 08
│   ├── acp_registry_adapter.py  # Phase 08
│   └── http.py              # Async HTTP client (Phase 08.5)
└── cli/commands/
    ├── backtrack.py          # Phase 08
    ├── security.py           # Phase 08
    ├── health.py             # Phase 09 scaffold
    └── acp.py               # Phase 08
```

Last validation commands:

- `.venv/bin/python -m pytest` — 186 passed (67 baseline + 66 Phase 08 + 20 async + 29 Event Store + 4 cache).
- `.venv/bin/python -m ruff check src tests` — clean.
- `.venv/bin/python -m compileall src tests` — passed.

Phase 08.5 complete ✅. All three workstreams delivered. Moving to Phase 09.