# Current Forge OS Phase

## Current Phase

- Phase: 07
- File: `plan/PHASE-07-adg-context.md`
- Status: not-started

## Current Objective

Make context deterministic and dependency-aware with artifact registration, an Artifact Dependency Graph, staleness detection, and token-budgeted pruning.

## Last Completed Phase

- Phase: 06
- File: `plan/PHASE-06-memory-lessons.md`
- Status: complete

## Resolved Decisions

1. Runtime: Python 3.11+.
2. Package import name: `forge_os`.
3. Preferred CLI command: `forge`.
4. Development package manager preference: `uv`, while preserving standard `pip` compatibility.
5. Distribution: local Python package first, `pipx` when ready, standalone binary later.
6. Adapter priority:
   1. `DummyAdapter`
   2. `ClaudeCodeAdapter`
   3. `CodexAdapter`
   4. `OpenClawAdapter`
   5. `OpenCodeAdapter`
   6. `LocalLLMAdapter`
   7. `HumanAdapter`
7. OpenClawAdapter architecture: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
8. Core state ownership: Forge OS core is the sole writer of canonical state.
9. Open formats: YAML, JSON, JSON Lines, Markdown, and GraphML.
10. Security baseline: least privilege, human approval for high-risk/destructive actions, explicit timeouts for executable checks.
11. Phase 01 CLI scaffold is complete with `forge init`, `forge status`, `forge config show`, `forge config validate`, and `forge explain`.
12. Phase 02 state machine is complete with `forge stage list/start/complete/advance/override`, atomic writes, transition validation, state markdown sync, and transition event logging.
13. Phase 03 events/hooks are complete with normalized lifecycle events, in-process event bus, hook registry, hook timeout/failure isolation, and `forge events list/tail`.
14. Phase 04 gates MVP is complete with file/pattern gates, severity handling, gate reports, `forge gate list/check/report`, gate events, persisted latest results, and stage advancement enforcement.
15. Phase 05 adapters/agents are complete with KernelAdapter interface, adapter registry/config placeholders, DummyAdapter, 12 stage personas, 4 cross-stage personas, output contracts, agent execution logs, `forge adapter list`, `forge agent list/contracts/run`, and optional `forge stage start --spawn-agent`.
16. Phase 06 memory/lessons are complete with YAML lesson store, reflection files, lesson add/list/approve/deprecate CLI, reflection list/show CLI, stage-completion reflection capture, pending lesson extraction queue, and approved high-confidence lesson injection into agent context.

## Blocking Questions

None currently.

## Notes For The Next Implementer

Read:

1. `BUILD_SPEC.md`
2. `plan/ORCHESTRATOR.md`
3. `plan/PHASE-07-adg-context.md`
4. `plan/PHASE-06-memory-lessons.md`
5. `plan/PHASE-05-adapters-agents.md`
6. `plan/KERNEL_ADAPTER_INTERFACE.md`
7. `plan/ADAPTER_ROADMAP.md`
8. `ARCHITECTURE.md`
9. `SCHEMAS.md`
10. Existing Phase 01-06 code under `src/forge_os/`
11. Existing tests under `tests/`

Phase 07 should implement ADG/artifact context only. Do not implement backtracking, daemon, channels, OpenClaw full integration, or plugins early.

Last validation commands:

- `.venv/bin/python -m pytest` — 61 passed.
- `.venv/bin/python -m ruff check src tests` — passed.
- `.venv/bin/python -m compileall src tests` — passed.
