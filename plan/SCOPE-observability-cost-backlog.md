# Scope — Observability / Cost / Remediation backlog (the deferred non-goals)

> **Status:** proposed (awaiting owner go/no-go). Companion to
> `plan/SCOPE-doctor-and-token-budget-cli.md`. These are the five items that scope deliberately
> deferred; the owner asked to scope them too.
> **How produced:** a fan-out — one researcher per feature grounded its scope in the real SRS text
> + code, then an adversarial critic trace-verified each (honest-trace, local-first/L004, layers,
> YAGNI). Every "looks-real-isn't" claim below was caught and corrected; corrections are folded in.
> **Constraints:** never mutate the core; strict layers; local-first/L004 (no required server/
> network/cloud); SRS-driven; owner-merge per slice.

---

## ⚠️ Shared foundation F0 — adapter cost events are not recorded in production today

The verification found that `AdapterSpawnStarted/Completed` events carrying real `usage` +
`total_cost_usd` are written to the Event Store **only when `event_store=` is injected into the
adapter — which happens only in tests.** The production construction path
(`adapters/registry.py::_claude_code_factory`) does **not** pass `event_store`, and recording is
gated `if self._event_store is None: return`. `agents/executor.py` has no event-store references.

**Net: in a real `forge agent run`, no spawn cost/usage events land in `events.db`.** Three of the
five features below read those events.

- **F0 (foundation, effort S):** inject the project's `event_store` into the adapter on the
  production spawn path (registry factory / executor) so spawn lifecycle + cost events are actually
  recorded. Additive; no core mutation. **Unblocks #1 (cost), #4 (cost cap), #2 (OTLP reasoning
  stream).** Also correct that only **`ClaudeCodeAdapter`** writes `AdapterSpawnCompleted` —
  `claude_raw`/`claude_sdk` are independent adapters that put `usage`/`total_cost_usd` on a
  *different* (NormalizedEvent) path; wiring their recording is part of F0 if their cost is wanted.

---

## Summary

| # | Feature | SRS trace | New FR? | Effort | Local-first | Recommendation |
|---|---------|-----------|---------|--------|-------------|----------------|
| 5 | **Per-session token monitor** (real FR-HD-003) | FR-HD-003, FR-TE-003 (verbatim fit) | no | **S** | clean | **build-now** — the honest version of the original ask |
| F0 | **Adapter event recording wiring** | enables FR-TE-001 | no | **S** | clean | **build-now** — unblocks #1/#2/#4 |
| 1 | **`forge cost`** (token + $ by stream/stage) | FR-TE-001/004, FR-COST-002 (name it) | no | **M** | clean | **build-now, after F0** |
| 3 | **`forge doctor --fix`** (guarded auto-remediation) | **NEW FR-HD-007** | yes (+bump) | **M** | clean | **build-later** — after doctor FR-HD-006 *ships* |
| 4 | **Always-on daemon monitor** (budget/latency/cost-cap) | FR-HD-003/005, FR-COST-004 | no | **L** | clean | **build-later** — needs hook-timing prereq |
| 2 | **OTLP dual-stream tracing** | FR-OBS-001, FR-SEM-002 | no | **L** | optional dep | **build-later** — Production-tier; MVP subset only |

All five verified **trace-honest, local-first-OK, layers-OK** ("fixable" — none unsound) once the
corrections below are applied.

---

## #5 — Per-session token monitor (real FR-HD-003) · S · build-now

The honest version of what the token-budget question was really after. The measurement **already
exists**: `agents/executor.py` calls `ContextPruner.select(stage_id, token_budget=2000)` and gets
`ContextSelection.total_tokens` for every spawn. Add a pure evaluator that grades utilization and
emits a warning + event on overage.

- **SRS (verbatim fit):** FR-HD-003 "Measures injected-context token count per session and warns if
  it exceeds budget. **Overages logged**." + FR-TE-003 "warn at 80%, error at 100%." No new FR.
- **Design:** new `context/token_monitor.py::evaluate_session_budget(total_tokens, token_budget, *,
  warn_ratio=0.80) -> {ratio, level: ok|warn|error}`; executor calls it right after `select()`; on
  warn/error → `log.warning` + append a new `TokenBudgetExceeded` lifecycle event (reuses
  `new_event`/`append_event`, the exact `_append_agent_event` pattern). Never pauses the spawn
  (matches "never break a spawn"; FR-TE-003's "may pause" is a separate decision).
- **Files:** `context/token_monitor.py` (new), `events/model.py` (+`TokenBudgetExceeded` Literal —
  event model, *not* a canonical core schema), `agents/executor.py` (sync+async wire), tests.
- **Corrections folded in:** (a) the error-≥100% tier is **near-unreachable in the wired path** —
  `pruner.py` omits any artifact that would exceed budget, so a single `select()` is always ≤budget;
  keep the error tier in the *pure evaluator* (unit-tested) but document that wired spawns realistically
  only emit `warn`. (b) Name the config key explicitly (`features.token_monitor.warn_ratio`, default
  0.80) + add a malformed-value edge test (`features` is an unvalidated `dict[str,Any]`).
  (c) Health surfacing (optional Slice 3) must add a real `health/token_budget.py` `HealthChecker`
  subclass **+ its test** (every health entry is a `HealthChecker`) — or drop it and rely on
  `forge events`.
- **Slices:** S1 pure evaluator+tests · S2 EventType + executor wiring + spawn-path tests · S3 (opt)
  health surfacing via a real checker.

## F0 — Adapter event recording wiring · S · build-now

See the foundation box above. Inject `event_store` into the adapter on the production spawn path so
spawn lifecycle + `usage`/`total_cost_usd` events are recorded outside tests. Additive; unblocks
#1/#2/#4. Tests: a real `run_stage_agent` against a recording-enabled dummy/mock asserts an
`AdapterSpawnCompleted` lands in `events.db`.

## #1 — `forge cost` · M · build-now (after F0)

Read-only aggregation of recorded spawn token + $ cost, grouped by stage and stream.

- **SRS (existing, name it verbatim):** FR-TE-001 "Stored in audit ledger and event metadata";
  FR-TE-004 "`forge cost` shows production vs evolution spend separately"; FR-COST-002 "`forge cost`
  … expose this." No new FR.
- **Design:** `use_cases/cost.py::CostUseCases.report()` opens the Event Store via the existing
  `_shared.state_manager_for` → `state_manager.event_store` seam, `read_by_type("AdapterSpawnCompleted")`,
  folds `metadata.usage` + `metadata.total_cost_usd` into a `CostReport`; **joins Started→Completed by
  `run_id`** for stage attribution (the Completed event carries usage/cost but **no** `stage_id`; the
  scalar `stage_id` is only on Started). `cli/commands/cost.py` renders a Rich table + `--json` +
  `--stage`. One `add_typer` line.
- **Corrections folded in:** (a) depends on **F0** (else empty against real projects). (b) Only
  **`ClaudeCodeAdapter`** produces these events — say "production data = claude_code" not "all three
  claude adapters." (c) `total_cost_usd` can be `None` → sum $ only over present floats; always show
  token totals. (d) **Evolution (shadow/canary) and exploration (Dreamer/Skill-Miner) streams have no
  data source in code** (`grep`=0; Dreamer doesn't spawn) → render those columns "no data source yet,"
  never fabricate. (e) adapters without pricing (dummy/codex/openclaw/opencode/human) → "no kernel
  pricing," not faked 0.
- **Slices:** S1 `CostUseCases`+`CostReport` (production stream, run_id join, unit tests) · S2 CLI
  sub-app + honest empty evolution/exploration columns.

## #3 — `forge doctor --fix` (guarded auto-remediation) · M · build-later

Opt-in `--fix` for the doctor preflight: create venv, install deps, `forge init`, rebuild invalid
config. A **guarded mutator**: bare `forge doctor` stays read-only; `--fix` shows a dry-run plan,
per-action confirm, non-destructive defaults, refuses CI/no-TTY without `--yes`; each fix re-runs its
FR-HD-006 check to prove it worked.

- **SRS:** **NEW FR-HD-007 "Guarded Environment Auto-Remediation"** → §3.8 + changelog row + version
  bump. (Verified: no existing FR covers this.)
- **Reuses (verified):** `project.scaffold.initialize_project` (overwrite-aware) for init;
  `scaffold._build_config` for config rebuild; `SecurityAuditLog`/`SecurityAuditEntry` to audit the
  config rewrite; `load_config` to detect the invalid-config FAIL.
- **Corrections folded in:** (a) **gate on the doctor *implementation* PR being merged**, not just
  FR-HD-006 in the SRS (else the SRS describes a `DoctorReport` contract that doesn't exist). (b)
  Name the audit shape: `action="doctor_autofix_config_rewrite"`, `decision=ALLOWED`. (c) Separate the
  two guards: config-rewrite only fires when config is *already invalid* (non-destructive is trivial);
  `--force` is the lever for the *init* fix against an existing `.forge/`. (d) venv/deps/init fixes
  precede project existence → can't use the project-scoped audit log → disclose+print, don't fabricate
  a global audit sink. (e) Map each acceptance clause 1:1 to a named test.
- **Slices:** PR-1 SRS-only (FR-HD-007) · PR-2 remediation models + `use_cases/doctor.fix()` (dry-run/
  confirm/CI-guard/audit) · PR-3 CLI flags + exit-code/guard matrix.

## #4 — Always-on daemon monitor · L · build-later

A gated, default-off daemon task (mirrors the Observer pattern) that periodically checks the token
budget, hook latency, and a cost cap — surfacing `DaemonAlert`s and self-throttling near the cap.

- **SRS (existing, verbatim-verified):** FR-HD-003 (token budget), FR-HD-005 (hook latency,
  *alert-only* per v4.1), FR-COST-004 (always-on cost cap with self-throttle). No new FR.
- **Reuses (verified):** `daemon/tasks.py::build_scheduled_tasks` + `_observer_tasks` gating;
  `ScheduledTask` + `TaskRunner` failure isolation; `load_observer_config` template; `DaemonStateStore.add_alert`;
  `DaemonState` (`extra="allow"` → additive throttle flag is safe); `HealthChecker` ABC.
- **Corrections folded in:** (a) **FR-HD-005 hook timing is not recorded today** (`hooks/registry.py`
  has no timing) → **Slice 1 = instrument `_run_one`** is a blocking prerequisite; don't claim FR-HD-005
  done without it. (b) FR-HD-003 "per session" has **no session id at the pruner boundary** → define
  the session source first (thread a run id, or "session = daemon-observed window"); prefer reading the
  **existing `.forge/context-selections.jsonl`** the pruner already writes over adding a new Event Store
  write. (c) FR-COST-004's "5% of average monthly production budget" is **not implementable** (no
  production-budget field exists) → use an **absolute config cap** (e.g. `always_on_monthly_usd`); defer
  the percentage formula. (d) Skill Miner is only a persona, **not a daemon task** → out of the cap set;
  state that so "collectively" isn't silently narrowed.
- **Slices (6):** S1 hook-timing instrumentation (prereq) · S2 `HookLatencyHealthChecker` · S3
  per-session token checker · S4 `CostAggregator` + `HealthMonitorConfig` (alert-only) · S5 self-throttle
  flag honored by dreamer/observer/health tasks · S6 gate `_health_monitor_tasks` behind
  `features.health_monitor` (default off).

## #2 — OTLP dual-stream tracing · L · build-later (optional dep)

Turn the reasoning spans (Event Store adapter events, run_id-keyed) and runtime-audit spans
(`security-audit.jsonl`) into OpenTelemetry spans — **local JSONL sink by default**, OTLP export only
when an endpoint is configured. Adds `forge trace <id>` (FR-SEM-002 names it; absent today).

- **SRS (existing):** FR-OBS-001 (span emission + OTLP), FR-SEM-002 (`forge trace`, verbatim).
- **Local-first reconciliation:** default sink = `.forge/traces/spans.jsonl` (zero infra); the
  `opentelemetry-*` exporter lives in a **new optional `[tracing]` extra**, off by default, active only
  when `features.tracing.otlp_endpoint` is set. L004-clean.
- **Corrections folded in:** (a) **`SecurityActionAudited` is declared but never emitted** — the audit
  source is the **`security-audit.jsonl` file only** (read via `SecurityAuditLog.read_all`); emitting
  audit *events* is net-new, not a reuse. (b) **FR-OBS-001's "dashboard shows both streams" + a
  `network` audit-span source are NOT deliverable by a local CLI** → deliver the MVP subset (emit + local
  sink + optional OTLP + `forge trace`); explicitly defer the dashboard + network spans; do not claim
  FR-OBS-001 fully satisfied. (c) **Correlation gap:** reasoning spans keyed by `run_id`, audit by
  `audit_id`, no shared `session_id` — be honest about partial linkage; don't invent correlation. (d)
  **Don't add `TracingConfig` to `schemas/config.py`** (that's a canonical schema → "never mutate core");
  follow the `observer` precedent — a `load_tracing_config` consumer reads `features.tracing` from the
  free-form dict.
- **Slices:** S1 neutral Span model + correlation index · S2 local JSONL sink + `DualStreamTracer`
  (default off) · S3 `use_cases/observability.py` + `forge trace` · S4 (optional) OTLP exporter behind
  the `[tracing]` extra + gated daemon export task.

---

## Recommended sequencing (if greenlit)

1. **Originals first:** `forge doctor` (FR-HD-006, SRS 4.2 bump) + `forge health knowledge` (FR-HD-002)
   — already scoped in the companion doc.
2. **#5 per-session monitor** (S, clean) — smallest, highest-signal, no prereqs.
3. **F0 wiring** (S) → **#1 `forge cost`** (M) — F0 unblocks real cost data.
4. **#3 `forge doctor --fix`** (M) — only after the doctor command ships.
5. **#4 always-on monitor** (L) — starts with the hook-timing prerequisite slice.
6. **#2 OTLP** (L, optional) — last; Production-tier; MVP subset only.

Each item = SRS-traced `tasks/todo.md` gate, layer gates clean, adversarial review (Workflow + schema),
host + clean `python:3.12-slim` Docker, one reviewable PR per slice for owner merge.
