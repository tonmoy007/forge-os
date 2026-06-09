# Forge OS — Resume Prompt

> **Generated:** 2026-06-09 (checkpoint before context compaction)
> **Trigger:** Manual handoff after Phase 05.5 Slice 4 merge
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current Phase

**Phase 05.5** — ClaudeCodeAdapter (kernel-first, decision D5=B)
**File:** `plan/PHASE-05.5-claude-code-adapter.md`
**Status:** Slices 1, 1.5, 2, 3, 4 complete & merged. **Slice 5 (SecurityEnforcer pre-spawn) is next.**

> Phase 10 (Daemon/Dreamer/Lazy Context) stays **paused** pending `/STATUS.md` D4/D3 owner
> decisions. `plan/CURRENT_PHASE.md` is the live execution pointer.

## Project State

| Check | Status |
|-------|--------|
| Last commit | `ad4da31` — "Merge pull request #9 … Slice 4" |
| Branch | `main`, up to date with `origin/main`; working tree clean |
| Tests | **440 pass** (`pytest`), ruff clean, compileall clean — host + clean `python:3.12-slim` Docker (latest deps) + **GitHub CI** |
| CI | live: `.github/workflows/ci.yml` mirrors the Docker gate; gates every PR (green on #7/#8/#9) |
| Real kernel | `claude` v2.1.169 **is installed** on this dev host (`/home/tonmoy/.local/bin/claude`). Gold stream-json sample: `tests/fixtures/claude_code/real_text_run.jsonl` |

## Completed (kernel-first arc + ClaudeCodeAdapter slices)

| Area | Deliverable | PR |
|------|-------------|----|
| Kernel contract | `kernel/types.py` (IKernelAdapter, NormalizedEvent, KernelCapabilities, …) | #1 |
| 5 adapters + bridge + harness | `human`/`claude_raw`/`claude_sdk`/`codex`/`opencode`; `adapters/bridge.py` (`AsyncToSyncBridge`); `harness/` | #1–#2 |
| **Slice 1** | `tool_map.py`, `runner.py` (subprocess + stream-json), `adapter.py` skeleton (P055.01–05) | (190539d) |
| **Slice 1.5** | Reconciled to the REAL claude contract — correct envelopes, required `--verbose`, dropped nonexistent `--max-turns`, records real usage/cost. **L007** | #7 |
| **Slice 2** | `hooks.py` (`.claude/settings.json` lifecycle) + event-store recording (`AdapterSpawnStarted`→N×`AdapterStreamEvent`→`Completed`/`Failed`, per-spawn `run_id` on handle metadata) (P055.06–08) | #3 |
| **Slice 3** | `replay.py` — `ClaudeCodeAdapter.replay_session(run_id)` re-projects the event stream, no subprocess (P055.09–10) | #5 |
| **Slice 4** | Fixed `_claude_code_factory` (binary check + correct params), threaded `--model`, `forge adapter status` (`use_cases/adapters.py`), bridge `optional_capabilities` (P055.11–12) | #9 |
| CI + repo hygiene | `.github/workflows/ci.yml`; committed `.claude/rules/`; gitignored tool-local `.claude/` state | #4/#6/#8 |

### Lessons in force (`tasks/lessons.md`): L001–L007
- L001/L005 — inject `forge_dir` for `~/.forge/` test isolation
- L002 — ruff E741 (no `l`/`O`/`I`); L003 — SQLite WAL + synchronous=NORMAL
- L004 — no server/network/cloud deps (local-first)
- L006 — validate in clean Docker (latest deps) before claiming green
- **L007 — verify an external tool's real contract (capture a gold sample + confirm flags) before building an adapter on assumptions; mock-only tests can't catch a wrong contract**

## Pending — remaining ClaudeCodeAdapter slices (`plan/PHASE-05.5-claude-code-adapter.md`)

| ID | Slice | Deliverable |
|----|-------|-------------|
| P055.13 | 5 | `SecurityEnforcer` check **before** the subprocess spawns: in `adapters/claude_code/adapter.py::spawn_agent`, call the enforcer's validate before `run_claude`; on DENY raise `ClaudeCodeSpawnError` |
| P055.14 | 5 | Tests: deny policy blocks the spawn; an audit entry is written to `.forge/security-audit.jsonl` |
| P055.15 | 6 | `forge init --adapter claude-code` bootstrap (+ `--permission-mode`); verify `claude` on PATH with a version check |

After the slices: Phase-05.5 exit checklist (incl. a real `forge agent run` with `default_adapter: claude_code` end-to-end — the kill criterion), then the **open-source launch** milestone (license — recommend Apache-2.0 — + README rewrite, per D5), then re-gate at `/STATUS.md` before Phase 10.

## Discipline (every commit) — non-negotiable
- Validate in **Docker** (`python:3.12-slim`, latest deps) before claiming green — L006. CI now enforces this too.
- One logical task per commit/PR; reference the task ID (e.g. `P055.13`). Branch from `main`, never commit to `main` directly; merge via PR (CI gates it).
- Capture lessons in `tasks/lessons.md` **before** fixing, when corrected by the user.
- Trace work to an SRS requirement (`plan/v4/SRSv4.1.md`): Slice 5 → security baseline / FR-NEG (policy/governance) + ADR (least privilege, human approval for destructive actions).
- Never `git add -A`; stage explicit files. After merge: `git remote prune origin`, delete the local branch.
- After each slice: run the adversarial review workflow (4 dimensions × per-finding verify), fix confirmed findings, re-validate.

## Suggested Next Prompt (Slice 5)

```
Implement Phase 05.5 Slice 5 — SecurityEnforcer pre-spawn check (P055.13–14):
1. First, LOCATE the SecurityEnforcer API: grep src/forge_os for "SecurityEnforcer",
   "validate_action", and the security-audit log writer (likely src/forge_os/security/
   or core/, used by Phase 08 `forge security`). Read its validate signature + the
   audit-log path (.forge/security-audit.jsonl) and decision enum (ALLOW/DENY/HITL).
2. In adapters/claude_code/adapter.py::spawn_agent, BEFORE run_claude, call the enforcer
   to validate executing the claude subprocess (e.g. action "execute_command",
   capability="shell"). On DENY: record an AdapterSpawnFailed event (best-effort, as in
   Slice 2) and raise ClaudeCodeSpawnError; the enforcer writes the audit entry.
   Inject the enforcer (DI) so it's optional/testable — default None = no gate (keeps
   existing tests green), consistent with how event_store/hook_command are injected.
3. Tests (extend tests/test_adapters_claude_code.py): a deny policy blocks the spawn
   (subprocess.run NOT called — patch it and assert), and an audit entry is written.
   Mock the enforcer; don't depend on real policy files.
Read plan/PHASE-05.5-claude-code-adapter.md (Slice 5 section), tasks/lessons.md, and
BUILD_SPEC.md security rules first. Validate in clean python:3.12-slim Docker before the PR.
Run the adversarial review workflow after implementing; CI gates the PR.
```
