# Forge OS Phase Orchestrator

This directory splits the Forge OS build into independent phase files. The goal is to let an implementer work phase by phase without remembering the full roadmap.

## Current Source Files

- `../BUILD_SPEC.md` — compact source of truth
- `CURRENT_PHASE.md` — current execution pointer
- `PHASE-00-foundation.md` through `PHASE-11-channels-openclaw-extensions.md` — detailed phase plans
- `KERNEL_ADAPTER_INTERFACE.md` — canonical language-agnostic adapter interface
- `ADAPTER_ROADMAP.md` — selected kernel adapter priority
- `OPENCLAW_ADAPTER_ARCHITECTURE.md` — OpenClaw integration boundary

## Operating Rules

1. Work one phase at a time.
2. Before starting a phase, read only:
   - `../BUILD_SPEC.md`
   - `CURRENT_PHASE.md`
   - The current phase file
   - Existing code/config directly related to that phase
3. Do not implement future-phase features early unless they are required as interfaces/stubs.
4. Every phase must end with:
   - Tests, if code exists
   - Diagnostics/build check, if available
   - Updated `CURRENT_PHASE.md`
   - Notes about incomplete or deferred items
5. Keep core deterministic. AI is an adapter, not the engine.
6. Preserve open file formats and human-readable state.
7. If a requirement is ambiguous, record a question in the phase file or `CURRENT_PHASE.md` instead of guessing.

## Execution Loop

For each phase:

1. Read current phase.
2. Confirm dependencies are complete.
3. Implement only listed deliverables.
4. Add/update tests.
5. Run checks.
6. Update the phase status.
7. Move `CURRENT_PHASE.md` to the next phase.

## Status Values

Use these values in `CURRENT_PHASE.md` and phase files:

- `not-started`
- `in-progress`
- `blocked`
- `review-needed`
- `complete`

## Phase Index

| Phase | File | Theme |
|---|---|---|
| 00 | `PHASE-00-foundation.md` | Architecture lock, schemas, repository decisions |
| 01 | `PHASE-01-cli-scaffold.md` | CLI, config, init, status, project layout |
| 02 | `PHASE-02-state-machine.md` | Pipeline state machine and transitions |
| 03 | `PHASE-03-events-hooks.md` | Event bus and lifecycle hooks |
| 04 | `PHASE-04-gates-mvp.md` | File and pattern gates |
| 05 | `PHASE-05-adapters-agents.md` | Kernel adapters, personas, output contracts |
| 06 | `PHASE-06-memory-lessons.md` | Reflections, lessons, project memory |
| 07 | `PHASE-07-adg-context.md` | Artifact graph and context pruning |
| 08 | `PHASE-08-backtrack-security.md` | Backtrack, rework, security baseline, ACP integration |
| 09 | `PHASE-09-health-global-skills.md` | Health checks, global memory, skill mining |
| 10 | `PHASE-10-daemon-dreamer-lazy-context.md` | Background daemon, Dreamer, lazy context |
| 11 | `PHASE-11-channels-openclaw-extensions.md` | Channels, OpenClawAdapter, extensions |

## Suggested User Prompt To Continue

Use this prompt whenever you want to continue implementation:

`Read BUILD_SPEC.md, plan/CURRENT_PHASE.md, and the current phase file. Implement the current phase only. Update CURRENT_PHASE.md when done.`
