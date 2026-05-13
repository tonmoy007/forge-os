# Forge OS — Resume Prompt

> **Generated:** 2026-05-12
> **Trigger:** Manual handoff requested
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current Phase

**Phase 10** — Daemon, Dreamer, Lazy Context
**File:** `plan/PHASE-10-daemon-dreamer-lazy-context.md`
**Status:** not-started (Phase 09 completed, Phase 10 queued)

## Project State

| Check | Status |
|-------|--------|
| Last commit | `d2cd147` — "fix: clean AGENTS.md phase index, move commit rules to ORCHESTRATOR.md" |
| Branch | `main` — up to date with `origin/main` |
| Tests | **230 pass** (`pytest`), ruff clean, compileall clean |
| Working tree | 1 modified file (in-progress refactor from another agent — DO NOT revert) |
| `CURRENT_PHASE.md` | **STALE** — still shows Phase 09 in-progress (🔄). Must update to Phase 10. |
| `AGENTS.md` | Up to date — Phase 09 ✅, Phase 10 🔲 |

### Working Tree Details

1. **Modified** `tests/test_adapters_async.py` — test renamed from `test_run_stage_agent_async_no_project` → `test_run_stage_agent_async_invalid_stage` with fixture and assertion changes. **Not your work — leave it alone.**
2. **Untracked** `.sisyphus/` — orchestration artifacts.
3. **Untracked** `plan/v4/KERNEL_UPDATED_PLAN.md`, `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — reference plan documents.

---

## Completed (Phase 09)

Phase 09 (Health, Global Memory, Skills) is fully complete across 5 commits:

| Commit | Description |
|--------|-------------|
| `0fc2732` | `forge health check` with 5 subsystem checkers (P09.01) |
| `d1c3476` | Global memory under `~/.forge/` with lesson promotion (P09.08) |
| `8d040b8` | Project profiles, pattern tracking, skill proposals, isolated forge_dir (P09.13-15) |
| `6650d91` | ACP agent health monitoring and session management (P09.18-22) |
| `6f6686c` | Hook harness, gate sims, knowledge scan, token report (P09.02-07, P09.17) |

### Lessons Captured

`tasks/lessons.md` contains L001–L005 covering:
- `~/.forge/` test isolation via injectable `forge_dir` (L001, L005)
- Ruff `E741` single-letter variable rule (L002)
- SQLite WAL + synchronous=NORMAL for local-first tools (L003)
- CocoIndex PostgreSQL dependency rejection (L004)

---

## Pending — Phase 10 Tasks

### Daemon Core
| ID | Task | Priority |
|----|------|----------|
| P10.01 | Implement daemon process model (background process, survives CLI exit) | High |
| P10.02 | Daemon state persistence to `~/.forge/daemon/state.json` | High |
| P10.03 | CLI commands: `forge daemon start/stop/status/logs` | High |
| P10.04 | Scheduled task runner (interval-based within daemon) | High |

### Dreamer
| ID | Task | Priority |
|----|------|----------|
| P10.05 | Dreamer daily digest (`pipeline/log/daily-YYYY-MM-DD.md`) | Medium |
| P10.06 | Weekly reflection re-ingestion for pattern detection | Medium |
| P10.07 | Lesson tension detection (conflicting lessons flagged) | Medium |
| P10.08 | Lesson confidence decay over time | Medium |
| P10.09 | Dormant lesson flagging (>30 days unused) | Medium |

### Observer & Health
| ID | Task | Priority | Depends On |
|----|------|----------|------------|
| P10.10 | Observer monitoring config + polling stub | Low | P10.04 |
| P10.11 | Daemon alerts in `forge status` | Low | P10.10 |
| P10.12 | ACP agent health as daemon scheduled task | High | P10.04, Phase 09 |
| P10.13 | Auto-recover failed ACP agents | High | P10.12 |
| P10.14 | Daemon-level agent uptime tracking (`~/.forge/daemon/metrics.json`) | Medium | P10.12 |

### Lazy Context
| ID | Task | Priority |
|----|------|----------|
| P10.15 | Skill menu injection (lazy-load) | Medium |
| P10.16 | On-demand skill expansion | Medium |
| P10.17 | Low-confidence lesson index | Low |
| P10.18 | Context budget enforcement during lazy loads | Medium |
| P10.19 | Context size reduction measurement | Low |

### Testing
| ID | Task | Priority |
|----|------|----------|
| P10.20 | Daemon/dreamer/lazy context tests | High |
| P10.21 | Daemon ACP monitoring tests | High |

---

## Decisions Not Yet Reflected

1. **CURRENT_PHASE.md must be updated** to reflect Phase 09 complete / Phase 10 in-progress and replace the stale Phase 09 task table.
2. **New modules to create:**
   - `src/forge_os/daemon/` — daemon process, state, scheduler
   - `src/forge_os/dreamer/` — digest, decay, tension detection
   - `src/forge_os/cli/commands/daemon.py` — `forge daemon` sub-app
   - `src/forge_os/cli/commands/dreamer.py` — `forge dreamer` sub-app
3. **Daemon architecture** (from phase plan):
   - Daemon layer sits above the existing engine layers
   - Scheduled task runner dispatches ACP health, Dreamer, Observer
   - Daemon state persisted to `~/.forge/daemon/state.json`
   - ACP metrics persisted to `~/.forge/daemon/metrics.json`
   - Signal handling: SIGTERM, SIGHUP
4. **ACP health monitoring** runs as a daemon scheduled task:
   - Registry check every 60s
   - Session list/cleanup every 5min
   - Agent restart on failure
5. **Daemon is optional** — core CLI must work without it

---

## Tests Expected to Fail

None. Current test suite is 230/230 green. Phase 10 implementation should add tests (P10.20, P10.21) and leave existing suite green.

---

## Suggested Next Prompt

```
Implement Phase 10: background daemon, Dreamer daily/weekly maintenance, lesson decay, lazy context builder, and ACP agent health monitoring as a daemon scheduled task. 

Start with:
1. Update CURRENT_PHASE.md to Phase 10
2. Create daemon module skeleton (P10.01-P10.04)
3. ACP health monitoring as daemon task (P10.12-P10.14)
4. Dreamer module (P10.05-P10.09)
5. Lazy context builder (P10.15-P10.19)
6. Tests and cleanup

See plan/PHASE-10-daemon-dreamer-lazy-context.md for full spec.
Read BUILD_SPEC.md, plan/ORCHESTRATOR.md, and tasks/lessons.md first.
Leave tests/test_adapters_async.py unchanged (in-progress work from another agent).
```
