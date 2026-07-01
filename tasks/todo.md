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
| OTLP dual-stream tracing | FR-OBS-001, FR-SEM-002 | Production-tier, optional dep, MVP subset only — a local CLI can't deliver dashboard/network spans |

## Done — `forge adapter enable/disable` (FR-KA-003, completed 2026-06-30)

Made FR-KA-003's acceptance ("user switches kernels by config change; no core code change") a
first-class command instead of hand-editing `.forge/config.yaml`. → PR #47 (merged). 3 confirmed
review findings fixed (vacuous list test, uncaught `OSError`→`ConfigError`, kebab normalization).

### Gate
1. **SRS:** FR-KA-003 (existing — acceptance: "User switches kernels by config change; no core code
   change required"). No new FR; this is the ergonomic surface over the existing `default_adapter` /
   `adapters.<id>.enabled` config fields.
2. **Files:** NEW `config/writer.py` (canonical atomic `save_config(path, config)`: tempfile +
   `os.replace`, `yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)` — same shape as the
   doctor `--fix` rewrite, now shared); `use_cases/adapters.py` (+`set_enabled(id, *, enabled,
   make_default)` returning an `AdapterMutation`); `cli/main.py` (+`adapter enable <id> [--default]` /
   `adapter disable <id>` on the existing `adapter_app`); tests NEW `tests/test_config_writer.py`,
   NEW `tests/test_cli_adapter.py`, extend `tests/test_use_cases_adapters.py`. **Core untouched** —
   `schemas/config.py` is read/dumped only; no `core/` or canonical-schema edits.
3. **Verify:** enable flips `enabled` + re-validates + persists; `--default` also sets
   `default_adapter`; disable flips back; **guard** — refuse to disable the current default; unknown
   id → error/exit 1; idempotent re-enable; enabling an unavailable adapter succeeds but warns with the
   probe reason; `forge config validate` still green after a write. Host + clean `python:3.12-slim`
   Docker.
4. **What breaks:** nothing existing — additive command + new writer module; read-only `adapter
   list/status` unchanged. Risk: a config rewrite drops YAML comments (round-trips through the schema,
   same as doctor `--fix`); the scaffolded config has none. Atomic write (tempfile + `os.replace`) so a
   crash mid-write can't truncate `config.yaml`.

## Active — Always-on daemon monitor (FR-HD-003/005, FR-COST-004, owner greenlit 2026-06-25)

Owner-authored scope: `plan/SCOPE-observability-cost-backlog.md` §#4. Default-off daemon task (Observer
pattern) that checks token budget, hook latency, and a cost cap — surfacing `DaemonAlert`s and
self-throttling. One PR per slice (6); start with the blocking prereq:
- [x] **S1 — hook-timing instrumentation (prereq)** — FR-HD-005 hook timing isn't recorded today. → PR #46 (merged).
- [x] S2 — `HookLatencyHealthChecker` → PR #48 (merged).
- [x] S3 — per-session token checker (reads the existing `.forge/context-selections.jsonl`) → PR #49 (merged).
- [x] S4 — `CostAggregator` + `HealthMonitorConfig` (alert-only; absolute config cap, not the
      unimplementable "% of monthly budget") → PR #50 (merged).
- [ ] S5 — self-throttle: cost-incurring daemon maintenance (Dreamer) skips + alerts near the cap (← this slice)
- [ ] S6 — gate `_health_monitor_tasks` behind `features.health_monitor` (default off)

### S1 gate
1. **SRS:** FR-HD-005 (existing — "Monitors hook execution time; persistently slow hooks flagged").
   No new FR; S1 is the recording prereq the checker (S2) reads.
2. **Files:** `hooks/registry.py` (+`HookResult.duration_ms`, measured in `_run_one`); NEW
   `hooks/timing.py` (`HookTiming` + `HookTimingLog` append/read `.forge/hook-timings.jsonl`);
   `events/bus.py` (best-effort record after `run()`); `project/scaffold.py` (pre-create the jsonl);
   tests NEW `tests/test_hooks_timing.py` + extend `tests/test_events_hooks_phase03.py`.
   **Core untouched** — recording wires through `EventBus` (events/, not core/), so
   `core/state_manager.py` is not modified.
3. **Verify:** a hook's measured `duration_ms` ≥ 0 across success/timeout/failure; `HookTimingLog`
   round-trips + tolerates malformed lines; `emit` records only when hooks ran, best-effort (a
   recording failure never breaks `emit`). Host + clean `python:3.12-slim` Docker.
4. **What breaks:** nothing — additive field + new module + a best-effort append in `EventBus`; events
   with no registered hooks write nothing. Risk: per-emit I/O → gated on non-empty results + swallowed
   on error so it can never fail a state mutation.

### S2 gate
1. **SRS:** FR-HD-005 (existing — "Monitors hook execution time; persistently slow hooks flagged").
   Alert-only per v4.1 (no auto-disable). S2 reads the `.forge/hook-timings.jsonl` S1 records.
2. **Files:** NEW `health/hook_latency.py` (`HookLatencyHealthChecker(HealthChecker)` — reads via
   `HookTimingLog`, flags hooks whose mean duration ≥ threshold over ≥ min_samples runs); register
   `"hook_latency"` in `use_cases/health.py::run_full_check` (surfaces under `forge health check`);
   NEW `tests/test_health_hook_latency.py`. **Core untouched** — new checker module + one dict entry.
3. **Verify:** empty/missing timings → healthy ("nothing recorded yet"); a hook with mean ≥ threshold
   and ≥ min_samples → flagged (healthy=False) with names + mean/max in details + a recommendation; a
   one-off slow sample below min_samples → not flagged; thresholds injectable for deterministic tests;
   surfaces in the `forge health check` report. Host + clean `python:3.12-slim` Docker.
4. **What breaks:** nothing — additive read-only checker; if it raises, `run_full_check` already
   isolates each checker (reports "crashed", others still run). Default off-path: a project with hooks
   disabled has an empty jsonl ⇒ healthy.

### S3 gate
1. **SRS:** FR-HD-003 (existing — "Measures injected-context token count per session and warns if it
   exceeds budget; overages logged") + FR-TE-003 (warn 80% / error 100%). No new FR. Scope §#4 (b):
   "session" = one recorded selection; read the existing `.forge/context-selections.jsonl` the pruner
   already writes (no new Event Store write, no session id invented). Scope §#5 (c) mandates this as a
   real `health/token_budget.py` `HealthChecker`.
2. **Files:** NEW `health/token_budget.py` (`TokenBudgetHealthChecker(HealthChecker)` — tolerant read
   of the selection log, grades each via the existing `context/token_monitor.evaluate_session_budget`,
   warn ratio from `features.token_monitor.warn_ratio` via `resolve_warn_ratio`); register
   `"token_budget"` in `use_cases/health.py::run_full_check`; NEW `tests/test_health_token_budget.py`;
   `tests/test_health_phase09.py` count 6→7. **Core untouched** — reuses the §#5 evaluator; no new
   schema, no `core/` edits.
3. **Verify:** no selections → healthy; warn-tier (≥ ratio) and error-tier (≥100%) → flagged
   (healthy=False) with stage + ratio + level in details + a recommendation; ok selections not flagged;
   breaches sorted worst-first; malformed/partial lines skipped; warn ratio resolved from config (lower
   it → an ok selection breaches); surfaces in `forge health check`. Host + clean `python:3.12-slim`
   Docker.
4. **What breaks:** nothing — additive read-only checker reusing the merged evaluator; `run_full_check`
   isolates a crash. Empty/missing selection log ⇒ healthy (fresh project, or context selection unused).

### S4 gate
1. **SRS:** FR-COST-004 ("Always-On Cost Cap — … MUST NOT exceed a configurable always-on monthly
   budget per project (default: 5% of the project's average monthly production budget); daemon
   self-throttles when approaching cap"). **Deviations (scope §#4(c)), both documented in
   `health/cost_cap.py`:** (a) no production-budget field exists, so the "5% of monthly" formula is
   unimplementable → the cap is an absolute configured value `features.health_monitor.cost_cap_usd`;
   (b) the FR scopes the cap to the daemon components "collectively", but spawn events carry no
   daemon-vs-production origin marker and those components don't record cost-bearing spawns today → the
   cap meters TOTAL recorded spend ("Recorded spend"), with daemon-scoped attribution deferred until an
   origin marker exists. Alert-only this slice (self-throttle is S5). No new FR.
2. **Files:** NEW `cost/aggregator.py` (`CostAggregator` — domain sum of recorded
   `AdapterSpawnCompleted` `total_cost_usd` from the Event Store, so a `health/` checker can reuse it
   without importing `use_cases/cost.py`); NEW `health/monitor_config.py` (`HealthMonitorConfig` +
   tolerant `load_health_monitor_config(features)`, mirroring `resolve_warn_ratio`); NEW
   `health/cost_cap.py` (`CostCapHealthChecker` — approaching ≥80% / over ≥100% of cap); register
   `"cost_cap"` in `use_cases/health.py::run_full_check`; NEW tests for each + `test_health_phase09`
   count 7→8. **Core untouched** — new domain modules + one dict entry; reuses the merged Event Store.
3. **Verify:** aggregator sums priced spawns / skips unpriced+bool / zero when no events.db; config
   loader defaults off+uncapped and rejects malformed/non-positive caps; checker — no cap ⇒ healthy,
   within ⇒ healthy, ≥80% ⇒ approaching (flagged), ≥100% ⇒ over (flagged), cap resolved from config,
   surfaces in `forge health check`. Host + clean `python:3.12-slim` Docker.
4. **What breaks:** nothing — additive read-only modules; `run_full_check` isolates a crash. Default
   off-path: no `cost_cap_usd` configured ⇒ healthy/inert, so existing projects are unaffected.

### S5 gate
1. **SRS:** FR-COST-004 ("… daemon self-throttles when approaching cap"). No new FR. Inherits the two
   S4 deviations (absolute config cap; TOTAL recorded spend, so the throttle is a lifetime, not monthly,
   cap — sticky until the cap is raised, consistent with S4). **Interpretation (documented in
   `daemon/throttle.py`):** the scope names "dreamer/observer/health tasks", but the throttle target is
   the daemon's *cost-incurring* maintenance — the **Dreamer** tasks (digest/decay/reingest, the LLM
   consolidation surface). Observer tasks (ACP restart/health/metrics) are operational and must keep
   running when over budget; health-monitor tasks (S6) are the monitors that *detect* the overage —
   throttling either would be self-defeating, so both are intentionally excluded. Skill Miner is a
   persona, not a daemon task (scope §#4(d)) — out of scope.
2. **Files:** NEW `daemon/throttle.py` (`CostThrottle` — reuses `CostAggregator` + the resolved
   `HealthMonitorConfig.cost_cap_usd` + the checker's `CAP_WARN_RATIO`; `ThrottleDecision`; a stateless
   `throttle_gate(run, …)` that skips the inner run + emits a deduped `DaemonAlert` via
   `DaemonStateStore.add_alert` when throttled); `daemon/tasks.py` (`_dreamer_tasks` gains `forge_dir`,
   wraps each dreamer run in the gate); NEW `tests/test_daemon_throttle.py`; extend
   `tests/test_daemon_tasks.py`. **Core untouched** — new domain module + a wrapper in the task builder;
   no schema edits (`DaemonState`/`DaemonAlert` reused as-is; the alert is the observable signal).
3. **Verify:** `CostThrottle.evaluate` — no cap ⇒ not throttled; below `CAP_WARN_RATIO` ⇒ not throttled;
   at/above ratio and over cap ⇒ throttled; cap resolved from `.forge/config.yaml`; broken config ⇒
   uncapped (not throttled). `throttle_gate` — when throttled: inner run NOT invoked (sentinel proves
   it), returns `{"throttled": True, …}`, records exactly one deduped alert; when clear: inner run
   invoked, its result passes through, no alert; missing daemon state ⇒ best-effort (no crash, no
   alert). Dreamer tasks built by `build_scheduled_tasks` skip their side effect when over cap.
   Host + clean `python:3.12-slim` Docker.
4. **What breaks:** nothing when uncapped — no cap ⇒ `evaluate` returns not-throttled, the gate is a
   pass-through, dreamer runs exactly as before. Risk: a throttle gate that mis-evaluates could silently
   suppress the Dreamer → mitigated by the sentinel-proven "clear ⇒ inner runs" test and the uncapped
   pass-through test. The per-run cost read is a cheap `.forge/events.db` aggregation (no new I/O on the
   uncapped path beyond the existing S4 read, which returns early when no events.db exists).

## Done — `forge doctor --fix` (FR-HD-007, completed 2026-06-25)

Owner-authored scope: `plan/SCOPE-observability-cost-backlog.md` §#3. One PR per slice:
- [x] **PR-1 — SRS-only (FR-HD-007)** → PR #42 (merged). SRS 4.2→4.3 + §3.8 row; 8 acceptance clauses for 1:1 test mapping.
- [x] **PR-2 — remediation models + `use_cases/doctor.fix()`** (dry-run / confirm / CI-guard / audit) → PR #43 (merged). 7/11 review findings fixed.
- [x] **PR-3 — CLI flags + exit-code/guard matrix** → PR #44 (merged). 6/7 review findings fixed (incl. a clause-8 false-pass on a non-remediable FAIL).
- [x] **Follow-up — TTY test seam** (test-only): `_stdin_is_tty()` indirection + interactive confirm-decline tests, closing the last render/exit branch (`SKIPPED` + remaining FAIL → "still not ready"). No behavior change.

**FR-HD-007 complete (2026-06-25).** `forge doctor --fix` shipped across PRs #42–#44; all 8 acceptance clauses realized; core untouched; 13 confirmed review findings (3 real defects + 10 test gaps) fixed across the slices.

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
