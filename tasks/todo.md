# tasks/todo.md — CLI + Observability Backlog (post-Phase-11)

> Source of scope: `plan/SCOPE-doctor-and-token-budget-cli.md` + `plan/SCOPE-observability-cost-backlog.md`
> (planning PR #35, merged 2026-06-24). Build order: **doctor → health knowledge** → per-session
> monitor → F0 wiring → forge cost. Build-later (gated): doctor --fix, always-on monitor, OTLP.
> Owner constraint still in force: never mutate the core; one owner-merged PR per slice.

## PR-1 — `forge doctor` (FR-HD-006) — IN REVIEW
Environment/install preflight diagnostic, distinct from FR-HD-001 `forge health check`.

1. **SRS:** NEW **FR-HD-006** (§3.8). SRS bumped **4.1 → 4.2** + changelog row (doc-edit-first). ✅
2. **Files (additive + 1 main.py line):**
   - NEW `schemas/doctor.py` (`DoctorStatus`, `DoctorCheck`, `DoctorReport` — pure pydantic). ✅
   - NEW `health/doctor.py` (`EnvironmentDoctor`: python/venv/install/deps + project config/writable). ✅
   - NEW `use_cases/doctor.py` (`DoctorUseCases`: composes domain doctor + reuses `AdapterUseCases.status()`; best-effort project resolution; never raises). ✅
   - NEW `cli/commands/doctor.py` (`doctor_app`, `forge doctor [--path] [--json]`, exit-code). ✅
   - MODIFY `cli/main.py` — import + `app.add_typer(doctor_app, name="doctor")`. ✅
   - TESTS: `tests/test_health_doctor.py`, `tests/test_use_cases_doctor.py`, `tests/test_cli_doctor.py` (25). ✅
3. **Verify:** 25 new unit tests (exit-code matrix, monkeypatched FAIL/WARN, no-project degrade-to-INFO, `--json` parse, broken-config-doesn't-raise); full suite **819 passed**; ruff + compileall clean; layer gates clean (health↛use_cases verified — adapter reuse lives in the use case; schemas pure; no new state.json/forge_dir hit); live `forge doctor` smoke in/out of project + `--json`. Docker (`python:3.12-slim`) validation. Adversarial Workflow review (5 dims × per-finding verify).
4. **What breaks:** nothing existing — new top-level command. Inside a project it reuses already-tested `AdapterUseCases`/`load_config`; outside one it must NOT call them (handled via best-effort resolution). Host-dependent env introspection guarded by injection/monkeypatch for determinism.

## PR-2 — `forge health knowledge` (FR-HD-002) — NEXT
Surface the orphaned `KnowledgeUseCases` (integrity scans + artifact-budget aggregate) on the
existing `health_app`. Existing requirement — no SRS bump.

---

# Archive: Phase 11 — Channels, OpenClaw, Extensions — COMPLETE 2026-06-24

> Phase 12 (integration & perf testing) complete 2026-06-15 (PRs #24–#28).
> Owner directed Phase 11 start 2026-06-22 (Path A: continue local-first forge-os; Path B —
> separate `aegis` service embedding forge-os — deferred). Hard owner constraint for this
> phase: **never mutate the core** (`core/` StateManager + existing `schemas/` contracts).
> New capability enters only through extension seams / new sibling modules / new schema files.

## Slices → PRs (sequential; main is owner-merge-only)

| Slice | PR branch | Tasks | SRS |
|-------|-----------|-------|-----|
| S1 — Extensions/plugins (keystone) | `feat/phase11-extensions` | P11.15-19 | FR-EXT-001/002/003/004, FR-KA-003 |
| S2 — Channels | `feat/phase11-channels` | P11.01-07 | FR-CH-001/002/003/004/005 |
| S3 — OpenClaw (interface + mocks) | `feat/phase11-openclaw` | P11.08-14 | FR-OCA-001..006 |

S1 first: it is the Aegis-convergent keystone (= Aegis Sprint 2.1) and the delivery seam for
the additive backlog (`plan/.../ADDITIVE-BACKLOG.md`), so additive items later land as
plugins without touching the core.

## Gate answers (phase level)

1. **SRS:** FR-EXT-001..004, FR-CH-001..005, FR-OCA-001..006, FR-KA-003
   (`plan/v4/SRSv4.1.md`); task IDs P11.01-19 (`plan/PHASE-11-channels-openclaw-extensions.md`).
2. **Files (all additive):**
   - S1: new `extensions/` domain module (manifest model, discovery, installer, validator,
     conflict detector); new `schemas/extension.py`; new `use_cases/extensions.py`; new
     `cli/commands/plug.py`; tests `tests/test_extensions_*.py`.
   - S2: new `channels/` domain module (channel adapter Protocol + `BaseChannelAdapter`,
     console channel, message normalizer, rate-limit/dedup); new `schemas/channel.py`; new
     `use_cases/channels.py`; new `cli/commands/channel.py`; tests `tests/test_channels_*.py`.
   - S3: new `adapters/openclaw/` (built on `kernel/acp_client.py::ACPClient`); new
     `use_cases/openclaw.py`; registered in `adapters/registry.py` (already a priority entry);
     tests `tests/test_adapters_openclaw.py`.
   - Shared: one `app.add_typer(...)` line each in `cli/main.py`; feature flags
     `features.plugins` / `features.channels` already scaffolded (`project/scaffold.py:77-79`).
   - **Untouched:** `core/`, existing `schemas/*` contracts (owner constraint).
3. **Verify (per PR):** unit tests (S1: manifest parse/validate, install/remove roundtrip on
   `tmp_path`, permission validation via `SecurityEnforcer.validate_action`, conflict detect;
   S2: `on_message` normalization, read-only status, feedback→triage queue, rate-limit/dedup,
   default-deny tool exec; S3: persona→OpenClaw config map, webhook→LifecycleEvent bridge
   mocked, offline fallback chain). Full suite + ruff + compileall + clean `python:3.12-slim`
   Docker (L006) + CI on every PR. Adversarial review per PR. Manual smoke: `forge plug
   list/install/remove` on a sample local extension; `forge channel` console roundtrip.
4. **What could break:**
   - Extensions MUST NOT bypass the state machine or override core/memory without consent
     (FR-EXT-003) → permission validation **fail-closed**.
   - Channel messages MUST NOT spawn agents / do file IO / run bash unless explicitly allowed
     (FR-CH-004) → **default-deny**; untrusted-input envelope (FR-SEC-005).
   - OpenClaw is OPTIONAL; unreachable/failed OpenClaw must not corrupt Forge state
     (FR-OCA-006) → fallback chain via ACP session mgmt.
   - New schema files must not alter existing contracts; feature flags default **OFF** so
     existing projects are unaffected until opted in.

## Discipline notes
- **Never mutate `core/` or existing `schemas/` contracts** (owner). New schema files only.
- `~/.forge/` or `.forge/` persistence MUST take injectable `forge_dir` (L001/L005); tests use `tmp_path`.
- No new server/network deps (L004). **FR-EXT-004 Sigstore remote signing deferred** — local
  install only this phase; document placeholder, default `--allow-unsigned` for local installs,
  emit `ExtensionUnsignedInstalled` event. Remote registry is excluded scope (Phase 08 owns ACP registry).
- Reuse `SecurityEnforcer` via DI (same pattern as adapters/event_store) for extension + channel perms.
- Channel adapter mirrors the `KernelAdapter` Protocol + `BaseKernelAdapter` pattern; console/dummy first (no network).
- OpenClaw: no concrete HTTP/WS API → interface + documented endpoint placeholders + mock tests only (phase scope allows).
- ruff: no `l`/`O`/`I` names (L002); WAL+synchronous=NORMAL if any sqlite (L003).

## Status
- [x] S1 extensions → PR #29 (merged) — `extensions/` + `schemas/extension.py` + `forge plug`
- [x] S2a channels read path → PR #30 (merged) — interface/console/normalize/status/broadcast
- [x] S2b channels write path → PR #31 (merged) — identity binding, default-deny, feedback, rate-limit
- [x] S3 openclaw (iface+mocks) → PR #33 (merged) — `adapters/openclaw/` + `schemas/openclaw.py`,
      registry factory; surfaced via existing `AdapterUseCases.status` (no `use_cases/openclaw.py`
      needed — every kernel adapter is surfaced this way). 50 tests; 9 review findings fixed.
- [x] Integration/closeout: `CURRENT_PHASE.md` → Phase 11 complete; `AGENTS.md §2` index
      (10/11/12 → ✅); PHASE-11 exit checklist ticked; `tasks/lessons.md` L009; `plan/RESUME.md`
      refreshed.

## Review section (phase wrap)

**Phase 11 complete — 2026-06-24.** Channels, OpenClaw, and the extension/plugin system shipped
as four owner-merged PRs (#29, #30, #31, #33), Path A (local-first), **core never mutated**.

- **Outcome:** `forge plug list/install/remove`, `forge channel status/broadcast/feedback/pair/
  confirm`, and an optional `OpenClawAdapter` on the Phase 08 ACP foundation. 794 tests pass
  (host + clean `python:3.12-slim` Docker), ruff + compileall clean.
- **Discipline held:** SRS-traced per-slice gate; layer gates clean (domain↛cli, schemas pure);
  every slice adversarially reviewed (Workflow + JSON schema, per-finding verification) and
  Docker-validated; one reviewable PR per slice for owner merge.
- **What worked:** the Workflow+schema review caught 9 real S3 defects mock-only tests missed —
  notably a path-guard canonicalization bypass (now L009) and a malformed-payload escape.
- **Deferred (documented):** OpenClaw HTTP/WebSocket transport + auth + webhook payloads (P11.08)
  pending a concrete OpenClaw endpoint contract — interface, ACP-stdio transport, and mock tests
  ship now; no wire protocol was invented.
- **Next:** Phase 13 (docs & release engineering) is the last remaining roadmap phase; owner
  go/no-go recommended (Fork B).

---

# Archive: Phase 10 (Daemon, Dreamer, Observer, Lazy Context) — COMPLETE 2026-06-10

Delivered as 4 workstream PRs (#15 dreamer, #16 daemon, #17 lazy-context, #18 observer/ACP) +
integration PR. 649 tests, ruff/compile clean, host + clean Docker + CI per PR. SRS:
FR-BD-001..003, FR-DR-001..003, FR-ML-003, FR-LCB-001..004. Notable review catches: ACPClient
infinite-block receive, daemon zombie-child restart brick, double-start TOCTOU, alert spam.
Deferred (documented): stop-timeout SIGKILL escalation, use_count cap, lesson-dedup beyond
exact text, Windows daemon support, PID-reuse hardening. Full per-WS record in git history and
`plan/CURRENT_PHASE.md`. Phase 05.5 + OSS-launch records archived at merge `2092911` (PR #14).
