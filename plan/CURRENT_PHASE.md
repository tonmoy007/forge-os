# Current Forge OS Phase

> **Session Continuity:** If this session is interrupted, run `git log --oneline -5 && git diff HEAD && cat plan/RESUME.md 2>/dev/null || echo "No RESUME.md"` before continuing.
> Last validated: 133 tests passed, ruff clean (new/modified files), compileall clean.

## Current Phase

- Phase: 08.5
- File: `plan/PHASE-08.5-async-cocoindex.md`
- Status: in-progress

## Current Objective

Prepare Forge OS for the v4 architecture by migrating the `KernelAdapter` protocol from synchronous to asynchronous execution, evaluating and adopting CocoIndex as the incremental indexing engine for the Context Pruner, and laying groundwork for event-sourced state.

## Last Completed Phase

- Phase: 08
- File: `plan/PHASE-08-backtrack-security.md`
- Status: complete

## Discipline & Clean Code Enforcement (Phase 08+)

Before implementing any task, run:
```bash
git log --oneline -5
git diff HEAD
git status
cat plan/RESUME.md 2>/dev/null || echo "No resume needed"
```

All Phase 08+ implementations MUST follow:

| Rule | How to Verify |
|------|--------------|
| **CLI never imports domain directly** | `grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/` — **zero matches required** |
| **No upward imports from domain** | `grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/kernel/` — **zero matches required** |
| **Schemas are pure data** | `grep -rn "from forge_os" src/forge_os/schemas/ --include="*.py"` — **only stdlib/pydantic imports allowed** |
| **Every use case has tests** | `ls tests/test_use_cases_*.py` — must exist for each `src/forge_os/use_cases/*.py` |

Last validation commands:

- `.venv/bin/python -m pytest` — 67 passed.
- `.venv/bin/python -m ruff check src tests` — passed.
- `.venv/bin/python -m compileall src tests` — passed.

Expected test count after Phase 08: 120+ passed.

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
11. ACP Protocol: JSON-RPC 2.0 over newline-delimited JSON on stdio.
12. ACP Registry: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
13. ACP session features (list, resume, close) are stabilized as of April 2026.
14. ACP agents must be registered in the official ACP Registry at `github.com/agentclientprotocol/registry`.
15. ACP integration is additive — existing LiteLLMAdapter behavior is preserved.
16. ACP agent installation supports: binary archives, npx packages, and uvx packages per manifest.
17. ACP agents spawned by Forge OS must respect SecurityEnforcer policies.
18. Phase 01 CLI scaffold is complete with `forge init`, `forge status`, `forge config show`, `forge config validate`, and `forge explain`.
19. Phase 02 state machine is complete with `forge stage list/start/complete/advance/override`, atomic writes, transition validation, state markdown sync, and transition event logging.
20. Phase 03 events/hooks are complete with normalized lifecycle events, in-process event bus, hook registry, hook timeout/failure isolation, and `forge events list/tail`.
21. Phase 04 gates MVP is complete with file/pattern gates, severity handling, gate reports, `forge gate list/check/report`, gate events, persisted latest results, and stage advancement enforcement.
22. Phase 05 adapters/agents are complete with KernelAdapter interface, adapter registry/config placeholders, DummyAdapter, 12 stage personas, 4 cross-stage personas, output contracts, agent execution logs, `forge adapter list`, `forge agent list/contracts/run`, and optional `forge stage start --spawn-agent`.
23. Phase 06 memory/lessons are complete with YAML lesson store, reflection files, lesson add/list/approve/deprecate CLI, reflection list/show CLI, stage-completion reflection capture, pending lesson extraction queue, and approved high-confidence lesson injection into agent context.
24. Phase 07 ADG/context is complete with artifact registry, JSON ADG persistence, stale downstream propagation, deterministic spread-activation context pruning, context selection audit logs, artifact/context CLI commands, stale artifact display in `forge status`, and pruned context integration for agent spawns.
25. **Phase 08 CLI refactoring complete** — all Phase 08+ commands moved to `src/forge_os/cli/commands/` sub-modules (`backtrack.py`, `security.py`, `health.py`, `acp.py`). `main.py` slimmed from 1240→895 lines. Separation of concerns enforced for all future commands.

## Blocking Questions

None currently.

## Phase 08.5 Task Summary

### A: Async Adapter Migration (Independent)
| ID | Task | Status |
|---|---|---|
| P08.5.01 | Define async `KernelAdapter` protocol | 🔄 |
| P08.5.02 | Implement async `DummyAdapter` | 🔄 |
| P08.5.03 | Async adapter executor and agent runner | 🔄 |
| P08.5.04 | Add `aiohttp`/`httpx` as core async HTTP deps | 🔄 |
| P08.5.05 | Remove Phase 08 sync wrappers | 🔄 |

### B: CocoIndex Evaluation & POC (Independent)
| ID | Task | Status |
|---|---|---|
| P08.5.06 | Evaluate CocoIndex for incremental indexing | 🔄 |
| P08.5.07 | CocoIndex pipeline integration with Context Pruner | 🔄 |
| P08.5.08 | Tree-sitter based code chunking via `RecursiveSplitter` | 🔄 |

### C: Event Store Groundwork (Independent)
| ID | Task | Status |
|---|---|---|
| P08.5.09 | Event Store aggregate schema definition | 🔄 |
| P08.5.10 | Dual-write Event Store alongside `state.json` | 🔄 |

### Phase 08.5 Validation
| Item | Target |
|---|---|
| Tests pass | TBD |
| Ruff lint | clean |
| Compileall | clean |

## Notes For The Next Implementer

Read:

1. `BUILD_SPEC.md`
2. `plan/ORCHESTRATOR.md`
3. `plan/PHASE-08.5-async-cocoindex.md` — current phase plan
4. `plan/PHASE-08-backtrack-security.md` — completed phase for reference
5. `plan/PHASE-07-adg-context.md`
6. `plan/PHASE-05-adapters-agents.md`
7. `plan/v4/KERNEL_UPDATED_PLAN.md` — async research, ACP registry details
8. `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — CocoIndex evaluation details
9. `plan/KERNEL_ADAPTER_INTERFACE.md`
10. `plan/ADAPTER_ROADMAP.md`
11. `ARCHITECTURE.md`
12. `SCHEMAS.md`
13. Existing source under `src/forge_os/`
14. Existing tests under `tests/`

### Phase 08.5 Overview (Three Independent Workstreams)

| Workstream | Description | Key Files |
|---|---|---|
| **A: Async Migration** | Migrate KernelAdapter protocol to async, update DummyAdapter and executor | `adapters/base.py`, `adapters/dummy.py`, `agents/executor.py` |
| **B: CocoIndex** | Evaluate CocoIndex, integrate with Context Pruner for incremental indexing | `context/pruner.py`, `context/pipeline.py` (new) |
| **C: Event Store** | Design Event Store aggregate schema, dual-write alongside state.json | `events/store.py` (new), `events/model.py` |

These workstreams share **no code dependencies** and may be implemented in any order or by parallel agents.

### Deferred from Phase 08

- LiteLLMAdapter ACP integration + adapter fallback chain (P08.32-P08.35) — part of async migration workstream
- ADG cascade further enhancement — P08.04 basic implementation exists
- Full event-sourced state migration — deferred to later phases

### Clean Code Rules (Continuing from Phase 08)

All new Phase 08+ commands MUST live in their own file under `src/forge_os/cli/commands/<domain>.py`.
Each file exposes a Typer sub-app. Register with `app.add_typer()` in `main.py`.
Business logic belongs in `use_cases/`, not in CLI command files.

### Directory Structure (Phase 08.5)

```
src/forge_os/
├── adapters/
│   ├── base.py              # ⏳ Migrate to async KernelAdapter protocol
│   ├── dummy.py             # ⏳ Migrate to async DummyAdapter
│   └── ...
├── agents/
│   └── executor.py          # ⏳ Migrate to async executor
├── context/
│   ├── pruner.py            # ⏳ CocoIndex pipeline integration
│   └── pipeline.py          # 🆕 CocoIndex incremental indexing pipeline
├── events/
│   └── store.py             # 🆕 Event Store for dual-write persistence
└── kernel/                  # Phase 08 complete
    ├── acp_client.py
    └── acp_registry_adapter.py
```

Last validation commands:

- `.venv/bin/python -m pytest` — 133 passed (67 baseline + 66 Phase 08 new).
- `.venv/bin/python -m ruff check src tests` — clean for new/modified files.
- `.venv/bin/python -m compileall src tests` — passed.

Phase 08 validated ✅. All core deliverables complete.