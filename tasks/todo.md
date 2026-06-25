# tasks/todo.md — CLI + Observability Backlog (post-Phase-11) — COMPLETE 2026-06-24

> Source of scope: `plan/SCOPE-doctor-and-token-budget-cli.md` + `plan/SCOPE-observability-cost-backlog.md`
> (planning PR #35, merged 2026-06-24). All build-now items shipped as one owner-merged PR per slice;
> **core untouched** throughout; each adversarially reviewed (Workflow + JSON schema, per-finding
> verification) and host + clean `python:3.12-slim` Docker validated. **893 tests pass**, ruff +
> compileall clean.

## Delivered (all merged to main)

| PR | Feature | SRS | Notes |
|----|---------|-----|-------|
| #36 | `forge doctor` — environment/install preflight | **NEW FR-HD-006** (SRS 4.1→4.2) | distinct from FR-HD-001 project health; Docker caught a host-masked `click` dep bug → **L010** |
| #37 | `forge health knowledge` — integrity + artifact budget | existing FR-HD-002 | surfaces the orphaned `KnowledgeUseCases`; review fixed a traceback/path-leak on a corrupt store |
| #38 | Per-session token budget monitor | FR-HD-003 + FR-TE-003 | `context/token_monitor.py` + `TokenBudgetExceeded` event, wired sync+async; review fixed a dual-`ConfigError` spawn-break → **L011** |
| #39 | F0 — Event Store wired into the production spawn path | enables FR-TE-001 | `bind_event_store` seam; a real `forge agent run` now records spawn cost events |
| #40 | `forge cost` — token/$ by stage from recorded events | FR-TE-001/004, FR-COST-002 | joins Started→Completed by `run_id`; review hardened the untrusted-`events.db` read path (9 fixes) |

## Build-later — gated (no work without owner go; SRS step noted)

| Item | SRS | Why gated |
|------|-----|-----------|
| Always-on daemon monitor (budget/latency/cost-cap) | FR-HD-003/005, FR-COST-004 | needs a hook-timing prereq; FR-COST-004 "% of production budget" is unimplementable as written (no such field) |
| OTLP dual-stream tracing | FR-OBS-001, FR-SEM-002 | Production-tier, optional dep, MVP subset only — a local CLI can't deliver dashboard/network spans |

## Active — `forge doctor --fix` (FR-HD-007, owner greenlit 2026-06-25)

Owner-authored scope: `plan/SCOPE-observability-cost-backlog.md` §#3. One PR per slice:
- [x] **PR-1 — SRS-only (FR-HD-007)** → PR #42 (merged). SRS 4.2→4.3 + §3.8 row; 8 acceptance clauses for 1:1 test mapping.
- [x] **PR-2 — remediation models + `use_cases/doctor.fix()`** (dry-run / confirm / CI-guard / audit) → PR #43 (merged). 7/11 review findings fixed.
- [ ] **PR-3 — CLI flags + exit-code/guard matrix.** (this slice)

### PR-2 gate
1. **SRS:** FR-HD-007 (added in PR #42).
2. **Files:** `schemas/doctor.py` (+remediation models, pure); NEW `health/remediation.py`
   (planner + injectable `RemediationRunner`/`RemediationExecutor` seam); `use_cases/doctor.py`
   (+`DoctorFixUseCases.fix()`); NEW `tests/test_health_remediation.py` +
   `tests/test_use_cases_doctor_fix.py`. No CLI/`main.py` change (that is PR-3).
3. **Verify:** dry-run plans-but-mutates-nothing; confirm-yes applies / confirm-no skips per action;
   no-TTY/CI refuses without `--yes`; config rewrite only when config already invalid (+`.bak`
   backup + audit `doctor_autofix_config_rewrite`/`ALLOWED`); `--force` required to re-init over an
   existing `.forge/`; each fix re-runs its FR-HD-006 check and records the new status. Host + clean
   `python:3.12-slim` Docker.
4. **What breaks:** nothing existing — additive models + new domain module + new use-case class; the
   read-only `forge doctor` path is untouched. Risk: venv/deps fixes shell out (subprocess; pip hits
   the network) → isolated behind the injectable `RemediationRunner` so tests never mutate the host
   or hit the network; a freshly-created venv can't be entered by the running process, so the venv
   re-check verifies the `pyvenv.cfg` artifact instead of the inert process-scoped `check_virtualenv`
   (review fix).

### PR-3 gate
1. **SRS:** FR-HD-007 — clause 1 ("bare `forge doctor` never mutates") + clause 8 exit code.
2. **Files:** `cli/commands/doctor.py` (+`--fix/--yes/--force/--dry-run`, `_run_fix`, `_render_fix`,
   `_fix_exit_code`, `_fix_payload`); `tests/test_cli_doctor.py` (+fix matrix). No `main.py` change
   (doctor sub-app already registered); core untouched.
3. **Verify:** `--yes/--force/--dry-run` without `--fix` → exit 2; `--fix --dry-run` plans + mutates
   nothing; `--fix` under no-TTY without `--yes` → refused, exit 1; `--fix --yes` applies (exit 0); a
   failed repair → exit 1; `--fix --dry-run --json` shape. CLI apply tests inject a local fake runner
   (no subprocess/network). Manual smoke of `forge doctor --fix [--dry-run|--yes --force]`. Host +
   clean `python:3.12-slim` Docker.
4. **What breaks:** nothing — the bare read-only `forge doctor` path is unchanged (the new flags
   default off); only `--fix` mutates. `interactive` is `sys.stdin.isatty()`; under CliRunner stdin is
   not a TTY, so apply tests pass `--yes`.

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
