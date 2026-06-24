# Forge OS — Resume Prompt

> **Generated:** 2026-06-24 (CLI + Observability backlog complete)
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current State

**No phase is in progress — this is a clean stopping point.** After Phase 11 (Channels, OpenClaw,
Extensions, complete 2026-06-24), a scoped **CLI + Observability backlog** was planned (PR #35, two
trace-verified scope docs) and its **build-now chain delivered in full** — five owner-merged PRs,
core untouched throughout. Phases **00–12 are all complete**; only **Phase 13** (Documentation &
Release Engineering, Fork B) and the conditional Fork-A **A1** (commitgate extract) remain in the
phase index, plus the explicitly **gated** backlog items below.

| Check | Status |
|-------|--------|
| Branch | `main`, clean; all feature branches deleted + remote pruned |
| Tests | **893 pass**, 3 perf deselected; ruff + compileall clean — host `.venv` + clean `python:3.12-slim` Docker (L006) |
| Expected failing tests | **none** |

Authoritative status: `plan/CURRENT_PHASE.md` ("CLI + Observability Backlog … COMPLETE") and
`tasks/todo.md` (per-PR table + gated items). Scope of record:
`plan/SCOPE-doctor-and-token-budget-cli.md` + `plan/SCOPE-observability-cost-backlog.md`.

## What the CLI + Observability backlog delivered (all on main, core untouched)

- **`forge doctor` (#36, NEW FR-HD-006, SRS 4.1→4.2):** environment/install preflight, distinct from
  FR-HD-001 project health; reuses `AdapterUseCases.status()`. Docker caught a host-masked `click` dep
  bug → **L010**.
- **`forge health knowledge` (#37, FR-HD-002):** surfaces the orphaned `KnowledgeUseCases` (integrity
  scans + artifact token-budget) on `health_app`.
- **Per-session token monitor (#38, FR-HD-003 + FR-TE-003):** `context/token_monitor.py` +
  `TokenBudgetExceeded` event, wired sync+async, best-effort. Dual-`ConfigError` spawn-break fix → **L011**.
- **F0 — adapter event recording (#39, enables FR-TE-001):** `bind_event_store` seam +
  `create_adapter_from_config(*, event_store=...)`; a real `forge agent run` now records spawn cost
  events (only `ClaudeCodeAdapter` records; async path out of scope).
- **`forge cost` (#40, FR-TE-001/004, FR-COST-002):** read-only token/$ by stage, joining
  `AdapterSpawnStarted`→`Completed` by `run_id`; honest about source adapter, missing pricing, and
  no-data-source streams; hardened against a malformed `events.db`.

## Gated / build-later (no work without owner go)

- **`forge doctor --fix`** — guarded auto-remediation. **NEW FR-HD-007 (needs an SRS bump first).**
  Owner accepted the scope ("will do for now") but has not greenlit the build.
- **Always-on daemon monitor** — FR-HD-003/005, FR-COST-004 (the latter's "% of production budget" is
  unimplementable as written).
- **OTLP dual-stream tracing** — FR-OBS-001, FR-SEM-002; Production-tier, optional dep, MVP subset only.

## Standing constraints (carry into the next session)

- **Owner-merge-only:** `main` is merged solely by the owner. Open a PR per slice; never merge to main
  yourself ([[forge-os-main-merge-policy]]).
- **Path A** is the chosen direction (local-first forge-os). The "Aegis Lifecycle" enterprise roadmap
  is **deferred to a future Path B** (a separate `aegis` service embedding `forge_os`, never folded
  into the core). Core-safe additive catalog:
  `plan/Phase-by-Phase System Upgrade and Sprint Planning/ADDITIVE-BACKLOG.md`.
- **Never mutate the core** (`core/` StateManager + canonical `schemas/{config,state,security}.py`).
- **Docker-first** (L006), **SRS-traced** `tasks/todo.md` gate, **adversarial review via the Workflow
  tool + JSON schema** for any fan-out whose output you need ([[forge-os-agent-orchestration]]).
  Lessons **L001–L011** in force (L010: dependency checks enumerate *declared* deps, validate in clean
  Docker; L011: a best-effort spawn-path hook must catch broadly — `load_config` raises two unrelated
  `ConfigError` classes).

## Suggested Next Prompt

```
The CLI + Observability backlog build-now chain is complete (PRs #36–#40 merged); Phases 00–12 done.
Pick one, on owner go/no-go:
  (a) A gated backlog item — `forge doctor --fix` (add FR-HD-007 to the SRS first), the always-on
      daemon monitor, or OTLP tracing. Each: SRS step first, then one reviewable PR per slice.
  (b) Phase 13 (Documentation & Release Engineering, Fork B) — read plan/CURRENT_PHASE.md +
      plan/PHASE-13-docs-release-engineering.md + plan/PLAYBOOK.md, plan via the SRS-traced
      tasks/todo.md gate, execute one owner-merged PR per slice.
Keep the core untouched; review with a Workflow + schema; Docker-validate before claiming green.
```
