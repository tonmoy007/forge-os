# Phase 10 — Background Daemon, Dreamer, and Lazy Context

## Status

not-started

## Objective

Add optional always-on behavior: background daemon, Observer scheduling, Dreamer daily/weekly maintenance, lesson decay, and lazy context loading.

## Scope

Included:

- Optional daemon process
- Daemon start/stop/status commands
- Scheduled tasks
- Dreamer daily digest
- Weekly re-ingestion/tension detection
- Lesson decay
- Lazy skill menu
- Lazy lesson index
- Token budget guard

Excluded:

- Channel adapters
- OpenClaw
- Remote server/team deployment

## Dependencies

- Phase 09 complete

## Deliverables

1. `forge daemon start`.
2. `forge daemon stop`.
3. `forge daemon status`.
4. Dreamer daily digest.
5. Lesson decay.
6. Observer monitoring config foundation.
7. Lazy Context Builder.

## Tasks

| ID | Task |
|---|---|
| P10.01 | Implement daemon process model |
| P10.02 | Implement daemon state persistence |
| P10.03 | Add daemon CLI commands |
| P10.04 | Add scheduled task runner |
| P10.05 | Implement Dreamer daily digest to `pipeline/log/daily-YYYY-MM-DD.md` |
| P10.06 | Implement weekly reflection re-ingestion |
| P10.07 | Detect lesson tensions for human review |
| P10.08 | Apply lesson confidence decay |
| P10.09 | Mark dormant lessons |
| P10.10 | Add Observer monitoring config and polling stub |
| P10.11 | Add alert output to status |
| P10.12 | Implement skill menu injection |
| P10.13 | Implement on-demand skill expansion |
| P10.14 | Implement low-confidence lesson index |
| P10.15 | Enforce context budget during lazy loads |
| P10.16 | Measure context size reduction |
| P10.17 | Add daemon/dreamer/lazy context tests |

## Acceptance Criteria

- Daemon is optional; core CLI works without it.
- Daemon survives restart using persisted state.
- Dreamer creates daily digest if activity occurred.
- Dreamer proposes destructive changes but never applies them without approval.
- Dormant lessons are not injected into context.
- Lazy context reduces eager prompt size and respects budget.

## Exit Checklist

- [ ] Daemon commands work
- [ ] Dreamer digest works
- [ ] Lesson decay works
- [ ] Observer stub works
- [ ] Lazy context works
- [ ] Tests pass
- [ ] `CURRENT_PHASE.md` updated to Phase 11

## Suggested Next Prompt

`Implement Phase 10 only: optional daemon, Dreamer daily/weekly maintenance, lesson decay, Observer stub, and lazy context builder.`
