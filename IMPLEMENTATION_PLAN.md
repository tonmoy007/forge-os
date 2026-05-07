# Forge OS Implementation Plan

The full build plan is split into phase files under `plan/`.

Start here:

1. Read `BUILD_SPEC.md`.
2. Read `plan/ORCHESTRATOR.md`.
3. Read `plan/CURRENT_PHASE.md`.
4. Read `plan/KERNEL_ADAPTER_INTERFACE.md` if the phase touches kernel adapters.
5. Read `plan/ADAPTER_ROADMAP.md` if the phase touches adapter implementation order.
6. Read `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md` if the phase touches OpenClaw.
7. Work only on the phase referenced by `CURRENT_PHASE.md`.

## Phase Files

| Phase | File | Result |
|---|---|---|
| 00 | `plan/PHASE-00-foundation.md` | Architecture, schemas, ADRs, test strategy |
| 01 | `plan/PHASE-01-cli-scaffold.md` | CLI scaffold, init, status, config |
| 02 | `plan/PHASE-02-state-machine.md` | Deterministic pipeline transitions |
| 03 | `plan/PHASE-03-events-hooks.md` | Event bus and lifecycle hooks |
| 04 | `plan/PHASE-04-gates-mvp.md` | File/pattern gates and gate reports |
| 05 | `plan/PHASE-05-adapters-agents.md` | Kernel adapters, personas, output contracts |
| 06 | `plan/PHASE-06-memory-lessons.md` | Project memory, reflections, lessons |
| 07 | `plan/PHASE-07-adg-context.md` | ADG, staleness, context pruning |
| 08 | `plan/PHASE-08-backtrack-security.md` | Backtrack, rework, security baseline |
| 09 | `plan/PHASE-09-health-global-skills.md` | Health, global memory, skill mining |
| 10 | `plan/PHASE-10-daemon-dreamer-lazy-context.md` | Daemon, Dreamer, lazy context |
| 11 | `plan/PHASE-11-channels-openclaw-extensions.md` | Channels, OpenClaw, extensions |

## Execution Rule

Do not implement future phase functionality early. If a future feature needs to be referenced, create only an interface, placeholder schema, or TODO noted in the current phase.

## Current Phase

See `plan/CURRENT_PHASE.md`.
