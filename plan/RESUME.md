# Forge OS — Resume Prompt

> **Generated:** 2026-06-22 (mid Phase 11)
> **This is a valid prompt a fresh agent can follow to continue.**

---

## Current State

**Phase 11 — Channels, OpenClaw, Extensions: IN PROGRESS.** Driven as one reviewable PR per
slice (owner merges each). Decision context: **Path A** — continue the local-first forge-os
roadmap. The dropped-in "Aegis Lifecycle" enterprise roadmap was reconciled and is **deferred
to a future Path B** (a separate `aegis` service that *embeds* `forge_os` as a library; it must
never be folded into the core). See `plan/Phase-by-Phase System Upgrade and Sprint Planning/
AEGIS-VS-FORGEOS-GAP-ANALYSIS.md` and `ADDITIVE-BACKLOG.md` (both on main).

**Hard owner constraint:** *never mutate the core* — `core/` (StateManager) and the canonical
schemas (`schemas/config.py|state.py|security.py`) stay untouched. New capability enters only
via additive new files, new Phase-11 schema files, the adapter registry, the plugin system, or
one `cli/main.py` `add_typer` line per slice.

| Check | Status |
|-------|--------|
| Branch | `main`, clean (this checkpoint rides a `chore/` PR) |
| Tests | **747 pass**, 3 perf deselected; ruff + compileall clean — host `.venv` + clean `python:3.12-slim` Docker (L006) |
| Expected failing tests | **none** |

## Phase 11 progress

| Slice | SRS | PR | Status |
|-------|-----|----|--------|
| S1 — Extension/plugin system | FR-EXT-001..004 | #29 | ✅ merged |
| S2a — Channels: interface/console/normalize/status/broadcast | FR-CH-001/002/003, FR-SEC-005 | #30 | ✅ merged |
| S2b — Channels: identity binding, default-deny, feedback intake, rate-limit | FR-CH-004/005, P11.05/07 | #31 | ✅ merged |
| **S3 — OpenClawAdapter (interface + mocks)** | **FR-OCA-001..006, P11.08-14** | — | **NEXT** |
| Closeout — docs + exit checklist | — | — | after S3 |

Extensions + channels are fully delivered. What's shipped lives in `src/forge_os/extensions/`
and `src/forge_os/channels/` (+ `use_cases/{extensions,channels}.py`, `cli/commands/{plug,
channel}.py`, `schemas/{extension,channel}.py`). `forge plug list/install/remove` and
`forge channel status/broadcast/feedback/pair/confirm` work.

## Next — Slice 3: OpenClawAdapter (interface + mocks ONLY)

No concrete OpenClaw HTTP/WS API exists, so deliver **interface + documented endpoint
placeholders + mock tests only** (the phase plan's excluded-scope note allows this — do NOT
invent a wire protocol). Build on the Phase 08 ACP foundation.

Real seams (verified):
- `kernel/acp_client.py:44` `ACPClient`, `kernel/acp_registry_adapter.py:66` `ACPRegistryAdapter` — reuse for comms + session list/resume/close.
- `adapters/registry.py:57` `AdapterRegistry` + `ADAPTER_PRIORITY` — OpenClaw is currently a `PlaceholderAdapter` entry to replace with a real factory behind an optional-dep guard (mirror the `opencode`/`claude_raw` factories).
- `adapters/base.py:44` `KernelAdapter` / `kernel/types.py:129` `IKernelAdapter` / `adapters/bridge.py` — which interface to implement (+ bridge if async).
- `channels/` `ChannelAdapter` — FR-OCA-004 channel reuse.
- `project/security_enforcer.py:15` `validate_action` — FR-OCA-002 tool policy mapping.
- `context/registry.py` ADG — FR-OCA-005 sync-back-without-overwrite.
- Mirror `adapters/opencode/` package + test layout; test file `tests/test_adapters_openclaw.py` (all mocked, no network).

Acceptance: OpenClaw is OPTIONAL; its failure must not corrupt Forge state; it forwards gate
requests to Forge Core (never decides gates); its memory never overwrites source-of-truth.

After S3: **closeout** — update `plan/CURRENT_PHASE.md` (Phase 11 complete), the phase index in
`AGENTS.md §2`, `tasks/todo.md` status, `tasks/lessons.md` if any new lesson, refresh this
RESUME, run the exit checklist in `plan/PHASE-11-channels-openclaw-extensions.md`.

## Discipline (every commit) — non-negotiable

- **Owner-merge-only:** `main` is merged solely by the owner. Open a PR per slice; never merge
  to main yourself ([[forge-os-main-merge-policy]]).
- **Never mutate the core** (see above). New schema files / additive extension only.
- **Docker-first:** run the full suite in clean `python:3.12-slim` with latest deps before
  claiming green (L006).
- **SRS-traced** `tasks/todo.md` gate (4 questions) before multi-file work; task/SRS ID in every
  commit message. One logical slice per PR.
- **Adversarial review via the Workflow tool with a JSON `schema`** — it returns validated
  findings reliably. Do NOT use loose background `Agent` fan-out for work whose output you need:
  `feature-dev:code-architect`/general background agents returned only terse status lines
  ("Done.", "Ready.") this phase and lost their content ([[forge-os-agent-orchestration]]).
- Lessons to `tasks/lessons.md` BEFORE fixing when the user corrects you (L001-L008 in force).
- Git hygiene: never `git add -A`; after merge `git remote prune origin` + delete local branch.

## Suggested Next Prompt

```
Read plan/CURRENT_PHASE.md + plan/PHASE-11-channels-openclaw-extensions.md + this RESUME.
Build Phase 11 Slice 3 only: OpenClawAdapter on the Phase 08 ACP foundation — interface +
documented endpoint placeholders + mock tests ONLY (no real OpenClaw API). Reuse ACPClient,
ACPRegistryAdapter, and the ChannelAdapter. Open it as a PR for the owner to merge, then do
the Phase 11 closeout. Keep the core untouched; review with a Workflow + schema.
```
