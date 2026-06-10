# Forge OS — Resume Prompt

> **Generated:** 2026-06-10 (after Phase 05.5 completion)
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current State

**Phase 05.5 — ClaudeCodeAdapter: COMPLETE.** All slices (1, 1.5, 2–6) merged and the
**kill criterion passed**: a real `forge agent run --stage srs` with `default_adapter:
claude_code` produced an agent-written `SRS.md`, contract passed, outputs registered
(haiku, 6 tool uses, 73s, $0.08).

| Check | Status |
|-------|--------|
| Branch | `main`, working tree clean |
| Tests | **476 pass**, ruff clean, compileall clean — host + clean `python:3.12-slim` Docker (latest deps) + GitHub CI |
| CI | `.github/workflows/ci.yml` gates every PR |
| Real kernel | `claude` v2.1.170 on this host; gold fixtures in `tests/fixtures/claude_code/` |

## What Phase 05.5 delivered

- `adapters/claude_code/`: runner (real stream-json contract, `--model`, `--permission-mode`),
  hooks lifecycle, event-store recording (`run_id` streams), replay, SecurityEnforcer pre-spawn
  gate (fail-closed), output derivation from Write/Edit/NotebookEdit tool uses.
- `forge init --adapter claude-code [--permission-mode <mode>]` — binary verified up front;
  exactly one adapter enabled in config.
- `forge adapter status`; config-driven selection (`create_adapter_from_config`) fail-loud.
- Executor seam fixed for real kernels: `_stage_context` carries `required_outputs` +
  `execution_mode: "batch"`; adapter renders the batch directive.
- Lessons L001–L007 in force (`tasks/lessons.md`).

## Next Milestone — open-source launch prep (decision D5)

1. Add `LICENSE` (Apache-2.0 recommended; owner confirms).
2. Rewrite `README.md`: what Forge OS is (local-first, kernel-agnostic SDLC orchestration),
   quickstart (`pip install -e .`, `forge init --adapter claude-code`, `forge agent run`),
   adapter matrix, architecture pointer.
3. Then re-gate at `/STATUS.md`: D4/D3 are **owner decisions** before Phase 10
   (Daemon/Dreamer/lazy context) resumes.

## Discipline (every commit) — non-negotiable

- Docker validation (`python:3.12-slim`, latest deps) before claiming green — L006; CI enforces.
- One logical task per commit/PR; task/SRS ID in message. Branch from `main`; merge via PR.
- Lessons to `tasks/lessons.md` BEFORE fixing when corrected by the user.
- Never `git add -A`. After merge: `git remote prune origin`, delete local branch.
- Adversarial review workflow (4 dimensions × per-finding verify) for every substantive change.

## Suggested Next Prompt

```
Prepare the forge-os open-source launch (decision D5): add an Apache-2.0 LICENSE and
rewrite README.md (what it is, quickstart with forge init --adapter claude-code and
forge agent run, adapter matrix, architecture pointer). Read plan/CURRENT_PHASE.md and
/STATUS.md first. One PR, CI-gated. Flag D4/D3 in /STATUS.md as owner decisions
blocking Phase 10.
```
