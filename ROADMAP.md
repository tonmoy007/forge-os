# Forge OS Roadmap

## Release 0.1 — CLI MVP ✅

Target phases:

- Phase 00
- Phase 01
- Phase 02 partial
- Phase 04 partial

Outcome:

- Initialize a Forge project.
- Show project status.
- Move through minimal profile stages.
- Block advancement on missing required files.

## Release 0.2 — Standard Pipeline ✅

Target phases:

- Phase 02 complete
- Phase 03
- Phase 04 complete
- Phase 05 partial

Outcome:

- Full 12-stage standard pipeline.
- Events/hooks.
- File and pattern gates.
- `DummyAdapter` foundation.
- Adapter config placeholders for selected adapter order.

## Release 0.3 — Agent Execution ✅

Target phases:

- Phase 05 complete

Outcome:

- Provider-agnostic agent execution.
- Personas and output contracts.
- `DummyAdapter` stable.
- First real adapter work starts with `ClaudeCodeAdapter` after Phase 05 is stable.

## Release 0.4 — Memory and ADG ✅

Target phases:

- Phase 06
- Phase 07

Outcome:

- Reflections and lessons.
- Artifact dependency graph.
- Staleness and context pruning.

## Release 0.5 — Quality and Security 🔨 (In Progress)

Target phases:

- Phase 08 (Backtrack, Security, ACP)

Outcome:

- Backtrack ticket schema, YAML store, and CLI (list/plan/approve/run) ✅
- Rework planner with approval flow ✅
- ADG cascade generation (P08.04) — pending
- Stale flag cleanup after revalidation (P08.07) — pending
- Security profiles (YAML-defined, path/command restrictions) ✅
- Security enforcer with timeouts and audit logging ✅
- Security audit log (`.forge/security-audit.jsonl`) ✅
- ACP CLI commands scaffolded (discover/list/install/sessions/close-session) ⚠️
- ACPClient + ACPRegistryAdapter backend — pending
- ACPUseCases backend — pending (currently missing, CLI errors out)
- IKernelAdapter ACP enhancements — pending
- ExternalCommand gate evaluator — pending
- MetricThreshold gate evaluator — pending
- Phase 08 tests (target 120+, at 67 baseline) — pending

## Release 0.6 — Async & Incremental Indexing

Target phases:

- Phase 08.5 (Async Migration, CocoIndex Evaluation, Event Store Groundwork)

Outcome:

- Async KernelAdapter protocol (coexists with sync).
- Async DummyAdapter and agent executor.
- `aiohttp` dependency for async HTTP.
- CocoIndex POC — incremental re-indexing for Context Pruner.
- CocoIndex evaluation report (adopt / defer / replace).
- Tree-sitter based code chunking evaluation.
- Event Store schema with dual-write alongside `state.json`.
- Phase 08 sync wrapper cleanup.

## Release 1.0 — Stable Local Forge OS

Target phases:

- Phase 09

Outcome:

- Health checks.
- Global memory.
- Skill mining.
- CocoIndex-backed context indexing pipeline.
- ACP agent health monitoring.
- Local-first Forge OS ready for real projects.

## Release 1.5 — Always-On Forge OS

Target phases:

- Phase 10

Outcome:

- Optional daemon.
- Dreamer maintenance.
- Lazy context builder.

## Release 2.0 — Ecosystem Forge OS

Target phases:

- Phase 11

Outcome:

- Channel adapters.
- Optional OpenClawAdapter.
- Extension/plugin system.
