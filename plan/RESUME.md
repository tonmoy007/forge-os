# Forge OS — Resume Prompt

> **Generated:** 2026-06-10 (after Phase 10 completion)
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current State

**Phase 10 — Daemon, Dreamer, Observer, Lazy Context: COMPLETE.** Executed as four
agent-built workstreams (PRs #15-#18) plus an integration PR; each adversarially
reviewed, Docker-validated, CI-gated. Phase 05.5 (real ClaudeCodeAdapter, kill
criterion passed) and the OSS launch prep (Apache-2.0 + README) shipped earlier the
same day.

| Check | Status |
|-------|--------|
| Branch | `main`, working tree clean |
| Tests | **649 pass**, ruff clean, compileall clean — host + clean `python:3.12-slim` Docker + GitHub CI |
| Real kernel | `claude` v2.1.x; `forge agent run --stage srs` proven end-to-end |
| Daemon | optional; `forge daemon start` schedules heartbeat + dreamer (daily/weekly) + observer tasks (`features.observer`, default off) |

## What Phase 10 delivered

- `daemon/`: state store (atomic, `forge_dir`-injectable, deduped capped alerts),
  fixed-delay scheduler with task+callback failure isolation, POSIX process lifecycle
  (zombie reap, O_EXCL start lock, rotating log), CLI start/stop/status/logs/restart.
- `dreamer/`: daily digest, exponential lesson decay + reversible dormancy, usage
  tracking on injection, tension detection, weekly reflection re-ingestion — all
  propose-only. CLI digest/scan/decay.
- `observer/`: registry checks, stale ACP session cleanup, one-attempt agent restart,
  uptime/restart metrics; ACPClient gained a select-based receive timeout.
- `context/lazy`: skill menu, on-demand expansion, low-confidence lesson index, 25%
  budget guard with deterministic trimming; `lazy_context` in every stage spawn context;
  `forge context budget` / `lazy-stats`. Daemon alerts render in `forge status`.

## Next — owner decision required

Phase 11 (Channels, OpenClaw, extensions — `plan/PHASE-11-channels-openclaw-extensions.md`)
is outward-facing surface area. Before starting, resolve in `/STATUS.md`:
- **D4** — three named adopters/contributors (deferred to "after launch"; launch prep is
  done, so: publish the repo? announce where?).
- **D3** — kill-criteria values for whatever track starts next.

Alternative next moves if Phase 11 stays gated: publish/announce the repo (visibility
flip + v0.x tag is an owner action), or Phase 12 (integration/performance testing).

## Discipline (every commit) — non-negotiable

- Docker validation (`python:3.12-slim`, latest deps) before claiming green — L006; CI enforces.
- One logical task per commit/PR; task/SRS ID in the message. Branch from `main`; merge via PR.
- Lessons to `tasks/lessons.md` BEFORE fixing when corrected by the user (L001-L007 in force).
- Never `git add -A`. After merge: `git remote prune origin`, delete local branch.
- Adversarial review workflow (4 dimensions × per-finding verify) for every substantive change.
- Agent-fanout pattern (worked well for Phase 10): map seams → spec per workstream →
  parallel worktree agents → integrator validates/reviews/wires shared files → sequential PRs.

## Suggested Next Prompt

```
Read /STATUS.md and plan/CURRENT_PHASE.md. D4/D3 are resolved as follows: <owner fills in>.
Proceed with <Phase 11 | repo publication | Phase 12> accordingly.
```
