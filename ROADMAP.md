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
- ADG cascade generation — pending
- Stale flag cleanup after revalidation — pending
- Security profiles (YAML-defined, path/command restrictions) ✅
- Security enforcer with timeouts and audit logging ✅
- Security audit log (`.forge/security-audit.jsonl`) ✅
- ACP CLI commands scaffolded (discover/list/install/sessions/close-session) ⚠️
- ACPClient (JSON-RPC over stdio) — pending
- ACPRegistryAdapter (registry fetch + agent install) — pending
- IKernelAdapter ACP enhancements (spawn, list, session mgmt) — pending
- ExternalCommand gate — pending
- MetricThreshold gate — pending
- Phase 08-specific tests — not yet written

## Release 1.0 — Stable Local Forge OS

Target phases:

- Phase 09

Outcome:

- Health checks.
- Global memory.
- Skill mining.
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
