# tasks/todo.md — Phase 10: Daemon, Dreamer, Observer, Lazy Context

> Phase 05.5 complete (kill criterion passed); OSS launch prep merged (Apache-2.0).
> Owner directed Phase 10 resumption 2026-06-10 ("complete next phase").
> Execution: 4 workstreams, one PR each, parallel agent fanout for B/C/D after A.

## Workstreams → PRs

| WS | PR branch | Tasks | SRS |
|----|-----------|-------|-----|
| A — Daemon core | `feat/phase10-daemon-core` | P10.01-04 (+P10.20 partial) | FR-BD-001, FR-BD-003 |
| B — Dreamer | `feat/phase10-dreamer` | P10.05-09 (+P10.20 partial) | FR-DR-001/002/003, FR-ML-003 |
| C — Observer & ACP health | `feat/phase10-observer-acp` | P10.10-14 (+P10.21) | FR-BD-002, P09.18-21 daemonized |
| D — Lazy context | `feat/phase10-lazy-context` | P10.15-19 (+P10.20 partial) | FR-LCB-001/002/003/004 |

## Gate answers (phase level)

1. **SRS:** FR-BD-001..003, FR-DR-001..003, FR-ML-003, FR-LCB-001..004 (`plan/v4/SRSv4.1.md`);
   task IDs P10.01-P10.21 (`plan/PHASE-10-daemon-dreamer-lazy-context.md`).
2. **Files:** new `daemon/`, `dreamer/` domain modules; extensions to `memory/lessons.py`
   (decay/dormancy fields), `context/` (lazy builder), `project/status.py` (alerts);
   new `use_cases/{daemon,dreamer,lazy_context}.py`; new `cli/commands/{daemon,dreamer}.py`
   + `context` sub-app extension; tests per module (rule #5).
3. **Verify:** per-PR: unit tests (daemon lifecycle with mocked process, scheduler intervals
   with injected clock, digest/decay determinism, lazy budget enforcement), full suite,
   ruff, compileall, clean-Docker (L006), CI, adversarial review per PR. Manual smoke:
   `forge daemon start/status/stop` real process round-trip.
4. **What could break:** daemon must be OPTIONAL (acceptance: core CLI works without it) —
   no existing path may grow a daemon dependency; lesson schema gains fields → must stay
   backward-compatible with existing lessons.yaml files; `forge status` alert surfacing
   must not break when no daemon state exists.

## Discipline notes
- `~/.forge/daemon/` persistence MUST take injectable `forge_dir` (L001/L005).
- SQLite if used: WAL + synchronous=NORMAL (L003). No new server/network deps (L004).
- Dreamer proposes, never applies destructive changes without approval (acceptance).
- Scheduler tests: injected clock, no sleeps (testing rules).

## Status
- [x] Map seams (workflow `map-phase10` — 4 parallel explorers)
- [x] WS-B dreamer — PR #15 (review: 18 confirmed → 13 fixed, 3 rejected w/ reasons, 2 no-gap notes)
- [x] WS-A daemon core — PR #16 (review: 17 confirmed → 9 fixed + 4 documented, 4 rejected w/ reasons)
- [x] WS-D lazy context — PR #17 (review: 5 confirmed → all fixed)
- [x] WS-C observer/ACP — PR #18 (review: 17 confirmed → 14 fixed, 3 no-gap notes)
- [x] Integration PR: dreamer daemon tasks (FR-BD-003), `forge status` alerts (P10.11),
      exit checklist, CURRENT_PHASE → Phase 11 pointer, RESUME refresh

## Review section (phase wrap)

- 649 tests, ruff clean, compileall clean — host + clean python:3.12-slim Docker + CI
  on every PR.
- Exit-checklist smoke (real project, real daemon process): init → dummy agent run →
  digest written for the active day → decay/scan run → context budget/lazy-stats →
  daemon start: heartbeat + dreamer-digest/decay/reingest all executed on first tick →
  graceful stop. Daemon optional: every core path works without it.
- Notable review catches across the phase: ACPClient infinite-block receive (would have
  stalled the whole daemon), daemon restart bricked by zombie children, double-start
  TOCTOU, alert spam, contract-context gaps. All fixed with regression tests.
- Deferred (documented, not silent): stop-timeout SIGKILL escalation (spec'd fail-loud),
  use_count cap, lesson-dedup beyond exact text, Windows daemon support (POSIX-only this
  phase), PID-reuse hardening beyond zombie reap.

---

# Archive: Phase 05.5 + OSS launch records

Prior task records (Slices 1-6, kill-criterion fixes, OSS launch) are preserved in git
history at tag-point `2092911` (merge of PR #14) — see `plan/CURRENT_PHASE.md` for the
condensed per-slice record.
