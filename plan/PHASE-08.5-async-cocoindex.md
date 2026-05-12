# Phase 08.5 — Async Adapter Migration & CocoIndex Evaluation

## Status

complete

## Objective

Prepare Forge OS for the v4 architecture by migrating the `KernelAdapter` protocol from synchronous to asynchronous execution, evaluating and adopting CocoIndex as the incremental indexing engine for the Context Pruner, and laying groundwork for event-sourced state.

This phase bridges two foundational shifts identified in the v4 research:
1. **Async migration** — ACPClient, ACPRegistryAdapter, and the future multi-model router all require async. The current sync KernelAdapter protocol blocks them.
2. **Incremental indexing** — CocoIndex provides production-ready incremental data transformation that directly replaces the naive file-watching in the current Context Pruner.

## Scope

Included:

- Asynchronous `KernelAdapter` protocol definition
- Async `DummyAdapter` implementation
- Async adapter executor and agent runner
- `aiohttp`/`httpx` as core async HTTP dependencies
- CocoIndex evaluation and POC integration with Context Pruner
- CocoIndex-based incremental re-indexing pipeline for ADG artifacts
- Tree-sitter based code chunking (via CocoIndex `RecursiveSplitter`)
- Event Store aggregate schema definition (dual-write alongside `state.json`)
- Phase 08 sync wrapper removal (cleanup after async migration)

Excluded:

- Full event-sourced state migration (deferred to later phases)
- OPA policy engine integration (Phase 09+)
- gVisor sandbox (Phase 09+)
- Multi-model router implementation (Phase 09+)
- Engineering IR protobuf schemas (Phase 09+)
- Dreamer Agent / daemon (Phase 10)

## Dependencies

- Phase 08 complete (ACPClient, ACPRegistryAdapter, backtrack, security, gates)
- Python 3.11+ with `asyncio` standard library
- `aiohttp` (or `httpx`) added to dependencies
- `cocoindex` added to optional dependencies (for evaluation)

## Workstreams (Independent)

This phase contains three independent workstreams. They share no code dependencies and may be implemented in any order or by parallel agents.

### Workstream A — Async Adapter Migration
Goal: Migrate the adapter layer from sync to async without breaking existing consumers.

**Deliverables:**
1. Async `KernelAdapter` protocol with `spawn_agent`, `on_event`, `get_default_tools`, `supports` as async methods.
2. Async `DummyAdapter` implementation.
3. Async agent executor (`run_stage_agent` async variant).
4. Sync-to-async compatibility tests.
5. Phase 08 sync wrapper removal.

**File boundaries:** `adapters/base.py`, `adapters/dummy.py`, `agents/executor.py`, `tests/test_adapters_async.py`

### Workstream B — CocoIndex Evaluation & Adoption
Goal: Evaluate CocoIndex as the incremental indexing engine and adopt if viable.

**Deliverables:**
6. `cocoindex` added to optional dependencies.
7. CocoIndex POC pipeline for Context Pruner: incremental re-indexing of `pipeline/` artifacts.
8. Performance benchmark (full re-index vs delta-only).
9. CocoIndex evaluation report with recommendation (adopt / defer / replace).

**File boundaries:** `context/pruner.py` (modified), `context/pipeline.py` (new), `tests/test_context_cocoindex.py`, `plan/v4/COCOINDEX_DECISION.md`

### Workstream C — Event Store Groundwork
Goal: Lay foundations for event-sourced state without changing the current state.json authority.

**Deliverables:**
10. Event Store aggregate schema: event type definitions, aggregate boundaries.
11. Phase 08 event types registered in `events/model.py`.
12. SQLite-backed append-only event log.
13. Dual-write: every `StateManager.save()` also appends to Event Store.
14. Projection engine skeleton (`forge replay <event_id>`).
15. Consistency verification: Event Store replay matches state.json.

**File boundaries:** `events/store.py` (new), `events/model.py` (modified), `core/state_manager.py` (modified), `tests/test_event_store.py`

## Tasks

### Async Adapter Protocol

| ID | Task | Notes |
|---|---|---|
| P08.5.01 | Define async `KernelAdapter` protocol | All methods become `async def`; preserve backwards compat with sync version |
| P08.5.02 | Implement async `DummyAdapter` | Port from sync, add `asyncio` sleep instead of `time.sleep` |
| P08.5.03 | Add async `BaseKernelAdapter` | Convenience base with default implementations |
| P08.5.04 | Implement async agent executor | `run_stage_agent_async` in `agents/executor.py` |
| P08.5.05 | Migrate CLI agent commands to async | `forge agent run` uses async executor |
| P08.5.06 | Integrate ACPClient (Phase 08) as async adapter target | Wire `ACPClient` into the async adapter framework |
| P08.5.07 | Add sync-to-async compatibility test | Verify both code paths produce identical results |
| P08.5.08 | Remove sync wrapper after migration validated | Clean up temporary sync facades |

### Async Infrastructure

| ID | Task | Notes |
|---|---|---|
| P08.5.09 | Add `aiohttp` dependency | Required for `ACPRegistryAdapter` and `CocoIndex` connectivity |
| P08.5.10 | Add async HTTP utility module | `forge_os/kernel/http.py` with timeout, retry, error handling |
| P08.5.11 | Verify all existing sync tests still pass | No regression from async addition |

### CocoIndex Evaluation & POC

| ID | Task | Notes |
|---|---|---|
| P08.5.12 | Add `cocoindex` to optional dev dependencies | `pip install forge-os[cocoindex]` |
| P08.5.13 | Build CocoIndex pipeline POC: watch `pipeline/` directory | Incremental re-indexing of ADG artifacts |
| P08.5.14 | Measure: full re-index time vs CocoIndex delta-only re-index | Quantify performance gain |
| P08.5.15 | Evaluate Tree-sitter chunking quality via `RecursiveSplitter` | Compare against current full-file reads |
| P08.5.16 | Evaluate CocoIndex live mode for Background Daemon compatibility | Verify streaming file watcher works |
| P08.5.17 | Produce CocoIndex evaluation report | Decision: adopt / defer / replace |
| P08.5.18 | If adopt: Integrate CocoIndex into `ContextPruner.select()` | Replace naive file-reading with incremental pipeline |

### Event Store Groundwork

| ID | Task | Notes |
|---|---|---|
| P08.5.19 | Define Event Store aggregate schema | SQLite-backed append-only log with projection |
| P08.5.20 | Register new Phase 08 event types in `events/model.py` | `BacktrackTicketCreated`, `ReworkStarted`, etc. |
| P08.5.21 | Implement dual-write: Event Store + state.json | Both write; state.json still authoritative |
| P08.5.22 | Verify dual-write consistency | Event Store replay produces same state as state.json |
| P08.5.23 | Add basic projection engine skeleton | `forge replay <event_id>` re-derives state |

### Phase Completion

| ID | Task | Notes |
|---|---|---|
| P08.5.24 | Write async adapter tests | Coverage for async DummyAdapter, agent executor |
| P08.5.25 | Write CocoIndex integration tests | Mock pipeline directory, verify delta-only re-index |
| P08.5.26 | Write Event Store tests | Append, read, replay, dual-write consistency |
| P08.5.27 | Update `CURRENT_PHASE.md` to Phase 09 | Phase handoff |

## Acceptance Criteria

### Async Migration
- [ ] Sync and async adapters coexist without breaking existing Phase 01-08 functionality
- [ ] Async `DummyAdapter` produces identical agent handles to sync version
- [ ] ACPClient (Phase 08) integrates cleanly into async adapter framework
- [ ] All 67 existing tests still pass (no regression)
- [ ] No sync wrapper code remains after migration validated (P08.5.08)

### CocoIndex
- [ ] CocoIndex POC pipeline indexes `pipeline/` artifacts incrementally
- [ ] Delta-only re-index is measurably faster than full re-index on >10 file corpus
- [ ] Tree-sitter chunks are semantically coherent (function/class boundaries respected)
- [ ] Evaluation report completed with clear recommendation

### Event Store
- [ ] Event Store aggregate schema defined and reviewed
- [ ] Dual-write operational: every state.json write also appends an event
- [ ] Replay from Event Store produces identical state to state.json
- [ ] Phase 08 event types registered in `events/model.py`

## Exit Checklist

- [ ] Async `KernelAdapter` protocol defined and implemented (`P08.5.01`)
- [ ] Async `DummyAdapter` passes all existing tests (`P08.5.02`)
- [ ] Sync wrapper removed (`P08.5.08`)
- [ ] `aiohttp` dependency added (`P08.5.09`)
- [ ] CocoIndex POC built and evaluated (`P08.5.13-17`)
- [ ] CocoIndex evaluation report written (`P08.5.17`)
- [ ] Event Store schema defined (`P08.5.19`)
- [ ] Dual-write operational (`P08.5.21`)
- [ ] Phase 08 event types registered (`P08.5.20`)
- [ ] Tests pass (target: 160+ tests including existing 67)
- [ ] `CURRENT_PHASE.md` updated to Phase 09

## Key References

1. `plan/PHASE-08-backtrack-security.md` — ACPClient, ACPRegistryAdapter foundation
2. `plan/PHASE-07-adg-context.md` — Existing Context Pruner implementation
3. `plan/v4/KERNEL_UPDATED_PLAN.md` — Async ACP integration spec
4. `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — CocoIndex deep research
5. `plan/v4/SRSv4.1.md` — FR-ES-001-006 (Event Sourcing), FR-ADG-002-003 (Context Pruning)
6. `src/forge_os/adapters/base.py` — Current sync KernelAdapter protocol
7. `src/forge_os/context/pruner.py` — Current Context Pruner
8. `src/forge_os/events/model.py` — Event type definitions

## External Resources

- CocoIndex: https://github.com/cocoindex-io/cocoindex | https://cocoindex.io
- ACP Registry: https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json

## Suggested Next Prompt

`Implement Phase 08.5: async KernelAdapter protocol, async DummyAdapter, aiohttp integration, CocoIndex POC for Context Pruner incremental re-indexing, Event Store schema with dual-write, and Phase 08 sync wrapper cleanup.`
