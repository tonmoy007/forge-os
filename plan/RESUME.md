# Forge OS — Resume Prompt

> **Generated:** 2026-06-09
> **Trigger:** Manual handoff after Phase 05.5 Slice 2 merge
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current Phase

**Phase 05.5** — ClaudeCodeAdapter (kernel-first, decision D5=B)
**File:** `plan/PHASE-05.5-claude-code-adapter.md`
**Status:** Slices 1–2 complete & merged. Slice 3 (replay) is the next task.

> Phase 10 (Daemon/Dreamer/Lazy Context) remains **paused** pending the strategic
> review in `/STATUS.md` (D4–D8). Do not resume Phase 10 until kernel-first work
> concludes. `plan/CURRENT_PHASE.md` is the live execution pointer.

## Project State

| Check | Status |
|-------|--------|
| Last commit | `7b693aa` — "Merge pull request #3 … ClaudeCodeAdapter Slice 2" |
| Branch | `main` — up to date with `origin/main` |
| Tests | **404 pass** (`pytest`), ruff clean, compileall clean (host + clean `python:3.12-slim` Docker, latest deps) |
| Working tree | clean (`.claude/settings.local.json` + `.claude/scheduled_tasks.lock` are gitignored) |
| `CURRENT_PHASE.md` | current — reflects Phase 05.5 kernel-first active work |

---

## Completed (kernel-first arc, PRs #1–#3)

| Area | Deliverable |
|------|-------------|
| Kernel contract | `kernel/types.py` — EventKind, NormalizedEvent, ToolUseProposal, ToolResult, AgentPersona, KernelCapabilities, IKernelAdapter |
| Adapters | `human`, `claude_raw`, `claude_sdk`, `codex`, `opencode` (all `IKernelAdapter`, async-generator + proposal-boundary) |
| Bridge | `adapters/bridge.py` — `AsyncToSyncBridge` (IKernelAdapter → sync `KernelAdapter` Protocol) |
| Registry | all 6 adapters registered with optional-dep guards |
| Harness | `harness/comparison_harness.py` — multi-kernel benchmark |
| **ClaudeCodeAdapter Slice 1** | `tool_map.py`, `runner.py` (subprocess + stream-json), `adapter.py` skeleton (P055.01–05) |
| **ClaudeCodeAdapter Slice 2** | `hooks.py` (`.claude/settings.json` lifecycle) + event-store recording: `AdapterSpawnStarted` → N×`AdapterStreamEvent` → `AdapterSpawnCompleted`/`AdapterSpawnFailed` under a per-spawn `run_id` exposed on `AgentHandle.metadata` (P055.06–08) |

### Lessons Captured (`tasks/lessons.md`)

- L001 / L005 — `~/.forge/` test isolation via injectable `forge_dir`
- L002 — Ruff `E741` single-letter variable rule
- L003 — SQLite WAL + `synchronous=NORMAL` for local-first tools
- L004 — CocoIndex PostgreSQL dependency rejected
- L006 — validate in clean Docker (latest deps) before claiming green; own deprecated third-party test helpers

---

## Pending — remaining ClaudeCodeAdapter slices (`plan/PHASE-05.5-claude-code-adapter.md`)

| ID | Slice | Deliverable |
|----|-------|-------------|
| P055.09 | 3 | `replay_session(run_id)` — reconstruct `AgentHandle` from the recorded event stream, **no subprocess** (`adapters/claude_code/replay.py`) |
| P055.10 | 3 | Tests: replay from a fixture event store, assert no subprocess invoked |
| P055.11 | 4 | Gate integration: `forge run` selects ClaudeCodeAdapter when `claude` is on PATH + configured |
| P055.12 | 4 | `forge adapter status` command |
| P055.13 | 5 | `SecurityEnforcer` check before subprocess spawn |
| P055.14 | 5 | Tests: deny policy blocks spawn, audit entry written |
| P055.15 | 6 | `forge init --adapter claude-code` bootstrap + `--permission-mode` flag |

After the slices: re-evaluate against the Phase-05.5 exit checklist, then return to the `/STATUS.md` strategic gate before Phase 10.

---

## Discipline (every commit)

- Validate in **Docker** (`python:3.12-slim`, latest deps) before claiming green — L006.
- One logical task per commit; reference the task ID (e.g. `P055.09`).
- Capture lessons in `tasks/lessons.md` **before** fixing, when corrected.
- Trace work to an SRS requirement in `plan/v4/SRSv4.1.md` (Slice 3 → FR-ES-003 replay).
- Never `git add -A`; inspect untracked files and decide commit / gitignore / delete.

---

## Suggested Next Prompt

```
Implement Phase 05.5 Slice 3 (replay), P055.09–10:
1. adapters/claude_code/replay.py — replay_session(run_id) reads the
   AdapterSpawnStarted / AdapterStreamEvent / AdapterSpawnCompleted events
   from the Event Store and reconstructs the AgentHandle WITHOUT spawning a
   subprocess (FR-ES-003 / ADR-005 determinism).
2. tests/test_adapters_claude_code_replay.py — replay from a fixture event
   store; assert subprocess.run is never called and the handle matches the
   originally recorded run.
Read plan/PHASE-05.5-claude-code-adapter.md and tasks/lessons.md first.
Validate in clean python:3.12-slim Docker before opening a PR.
```
