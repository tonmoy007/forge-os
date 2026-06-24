# Forge OS — Resume Prompt

> **Generated:** 2026-06-24 (Phase 11 complete)
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current State

**No phase is in progress — this is a clean stopping point.** Phase 11 (Channels, OpenClaw,
Extensions) completed 2026-06-24 and merged to `main` (PRs #29, #30, #31, #33). Phases **00–12
are all complete**; only **Phase 13** (Documentation & Release Engineering, Fork B) and the
conditional Fork-A **A1** (commitgate extract) remain in the index.

| Check | Status |
|-------|--------|
| Branch | `main`, clean; all Phase 11 branches deleted + remote pruned |
| Tests | **794 pass**, 3 perf deselected; ruff + compileall clean — host `.venv` + clean `python:3.12-slim` Docker (L006) |
| Expected failing tests | **none** |

See `plan/CURRENT_PHASE.md` ("Phase 11 ... COMPLETE") and `AGENTS.md §2` (index now shows
10/11/12 ✅) for the authoritative status. Phase-wrap notes are in `tasks/todo.md`.

## What Phase 11 delivered (all on main, core untouched)

- **S1 extensions/plugins (#29):** `schemas/extension.py`, `extensions/`, `forge plug list/install/remove` (fail-closed permission gate).
- **S2a/S2b channels (#30/#31):** `schemas/channel.py`, `channels/` (`ChannelAdapter` Protocol, console, identity binding, default-deny policy, feedback intake + rate-limit), `forge channel status/broadcast/feedback/pair/confirm`.
- **S3 OpenClaw (#33):** `schemas/openclaw.py`, `adapters/openclaw/` — optional `OpenClawAdapter(IKernelAdapter)` on the Phase 08 ACP foundation; interface + documented placeholders + mock tests only. HTTP/WS transport + auth + webhook payloads deferred to **P11.08** (no concrete OpenClaw endpoint contract exists yet); the stdio ACP transport (`gateway_command`) is wired.

## Standing constraints (carry into the next session)

- **Owner-merge-only:** `main` is merged solely by the owner. Open a PR per slice; never merge to main yourself ([[forge-os-main-merge-policy]]).
- **Path A** is the chosen direction (local-first forge-os). The "Aegis Lifecycle" enterprise roadmap is **deferred to a future Path B** (a separate `aegis` service embedding `forge_os`, never folded into the core). Catalog of core-safe additive items: `plan/Phase-by-Phase System Upgrade and Sprint Planning/ADDITIVE-BACKLOG.md`.
- **Never mutate the core** (`core/` StateManager + canonical `schemas/{config,state,security}.py`).
- **Docker-first** (L006), **SRS-traced** `tasks/todo.md` gate, **adversarial review via the Workflow tool + JSON schema** for any fan-out whose output you need ([[forge-os-agent-orchestration]]). Lessons L001–L009 in force (L009: canonicalize path guards before comparison).

## Suggested Next Prompt

```
Phases 00–12 are complete. If the owner gives go/no-go for Phase 13 (Documentation & Release
Engineering, Fork B): read plan/CURRENT_PHASE.md + plan/PHASE-13-docs-release-engineering.md +
plan/PLAYBOOK.md, then plan it through the SRS-traced tasks/todo.md gate and execute one
reviewable PR per slice for owner merge. Otherwise, await direction. Keep the core untouched;
review with a Workflow + schema.
```
