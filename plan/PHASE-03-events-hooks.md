# Phase 03 — Event Bus and Lifecycle Hooks

## Status

complete

## Objective

Introduce a normalized internal event bus and hook system so future agents, gates, memory, and health checks can react without tight coupling.

## Scope

Included:

- Event model
- In-process event bus
- Hook registry
- Hook ordering
- Hook timeouts
- Hook error isolation
- JSONL event log

Excluded:

- External message queue
- Team/server event bus
- Real AI hook behavior

## Dependencies

- Phase 02 complete

## Deliverables

1. Event schema implementation.
2. Event bus.
3. Hook registry.
4. Lifecycle events wired to CLI/stage commands.
5. Event replay/debug command.

## Initial Events

- `SessionStart`
- `UserPromptSubmit`
- `StageStarted`
- `StageCompleted`
- `GateStarted`
- `GateCompleted`
- `Stop`
- `SubagentStop`
- `SessionEnd`
- `ArtifactChanged`

## Tasks

| ID | Task |
|---|---|
| P03.01 | Implement event model |
| P03.02 | Implement event ID/correlation ID generation |
| P03.03 | Implement JSONL event append |
| P03.04 | Implement in-process event bus |
| P03.05 | Implement hook registration |
| P03.06 | Implement hook execution order |
| P03.07 | Implement hook timeout behavior |
| P03.08 | Implement hook failure handling |
| P03.09 | Emit events from stage commands |
| P03.10 | Add `forge events tail/list` read-only command |
| P03.11 | Add mock hook tests |
| P03.12 | Add event serialization tests |

## Acceptance Criteria

- Hook failure does not crash stage execution.
- Events are normalized and append-only.
- Event order is deterministic.
- Stage commands emit expected lifecycle events.
- Events can be inspected from CLI.

## Exit Checklist

- [x] Event model exists
- [x] Event bus exists
- [x] Hooks register and run
- [x] Hook failures are isolated
- [x] Event CLI inspection works
- [x] Tests pass
- [x] `CURRENT_PHASE.md` updated to Phase 04

## Completion Notes

Phase 03 completed with normalized lifecycle events and in-process hook plumbing only.

Implemented:

- `forge_os.events` package.
- `LifecycleEvent` model with normalized JSONL serialization.
- Event ID and correlation ID support.
- JSONL event append/read/filter helpers.
- In-process `EventBus`.
- `forge_os.hooks` package.
- `HookRegistry` with deterministic ordering by order/name.
- Hook timeout behavior.
- Non-blocking hook failure isolation.
- Explicit blocking hook failure behavior.
- State transition event emission via `StateManager`.
- `forge events list`.
- `forge events tail`.
- Event serialization, hook ordering/failure/timeout, and event CLI tests.

Deliberately not implemented:

- External message queues.
- Team/server event bus.
- Real AI hook behavior.
- Full gate internals.
- Agents/adapters.
- Memory, ADG, backtracking, daemon, channels, OpenClaw, or plugins.

Validation run:

- `/tmp/forge-os-phase02-venv/bin/python -m pytest` — 37 passed.
- `/tmp/forge-os-phase02-venv/bin/ruff check` — passed.
- `python3 -m compileall src tests` — passed.

## Suggested Next Prompt

`Implement Phase 03 only: event bus, lifecycle hooks, event logging, and hook failure isolation.`
