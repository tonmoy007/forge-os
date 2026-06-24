# Current Forge OS Phase

> **Read order:** `/STATUS.md` → `/CLAUDE.md` → this file → the current phase file.
>
> **Session Continuity:** If this session is interrupted, run `git log --oneline -5 && git diff HEAD && cat plan/RESUME.md 2>/dev/null || echo "No RESUME.md"` before continuing.
> Last validated: 893 tests passed + 3 perf benchmarks (host `.venv` + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean — 2026-06-24 (Phase 11 + the post-Phase-11 CLI/Observability backlog complete; see the section below).
>
> The 2026-05-13 strategic pause was lifted 2026-06-10 by owner direction ("complete next
> phase") after the kernel-first arc (Phase 05.5) shipped and the OSS launch prep merged.

## Phase 10 — Daemon, Dreamer, Observer, Lazy Context: COMPLETE (2026-06-10)

Executed as four agent-built workstreams, each adversarially reviewed (4 dimensions ×
per-finding verification), Docker-validated, and merged via CI-gated PRs:

- **WS-A daemon core (PR #16, P10.01-04):** optional POSIX daemon (`forge daemon
  start/stop/status/logs/restart`), `DaemonStateStore` (atomic, `forge_dir`-injectable,
  capped+deduped alerts), fixed-delay `TaskRunner` with task AND callback failure
  isolation, zombie-reap + O_EXCL start lock, rotating log.
- **WS-B Dreamer (PR #15, P10.05-09):** daily digest (`pipeline/log/daily-*.md`, only on
  activity), exponential confidence decay + dormancy (<0.3 or 30d unused; reversible,
  never deletes), usage tracking on context injection, tension detection + weekly
  reflection re-ingestion (propose-only). `forge dreamer digest/scan/decay`.
- **WS-C Observer & ACP (PR #18, P10.10-14):** registry checks, stale-session cleanup,
  one-attempt agent restart, uptime/restart metrics (`daemon/metrics.json`) — registered
  as daemon tasks behind `features.observer` (default off). Phase 09 ACP session stubs
  implemented. Hardening: `ACPClient._receive` select timeout (hung agent can no longer
  stall the daemon), consecutive-alert dedup, client stop in `finally`.
- **WS-D lazy context (PR #17, P10.15-19):** skill menu + on-demand expansion,
  low-confidence lesson index, 25% lazy-share budget guard with deterministic trimming,
  `forge context budget` / `lazy-stats`, `_stage_context.lazy_context` (never breaks spawns).
- **Integration (this PR):** Dreamer tasks scheduled in the daemon (daily digest/decay,
  weekly re-ingestion — FR-BD-003), daemon alerts rendered in `forge status` (P10.11).

Exit checklist: all items pass — daemon round-trip with all 4 built-in tasks executing,
digest/decay/scan/budget/lazy-stats smoke on a real project, 649 tests, ruff, compileall,
clean Docker, CI. Daemon remains optional: core CLI works without it.

## Phase 12 — Integration & Performance Testing: COMPLETE (2026-06-15)

Delivered as a series of CI-gated PRs (each adversarially scoped, merged by the owner):

- **Integration suite** (`tests/integration/`, 22 tests): happy-path lifecycle walks
  (minimal + standard profiles), failure-path negative guarantees (gate block, agent
  contract failure, override audit, hook-timeout isolation, backtrack guard), the
  adapter-swap regression (Dummy / Human-via-`AsyncToSyncBridge` / mocked-ClaudeCode →
  byte-identical canonical state, ADR-005), and a golden gate-evaluation dataset (all four
  gate types × pass/fail/warn).
- **Perf harness** (`tests/perf/`, marked `perf`, deselected by default so PR CI stays
  fast): NFR benchmarks asserting SRS §5.1 — hook dispatch <200ms (0.26ms), context
  injection <500ms / ≤2000 tok (0.38ms), stage transition <1s (46ms). First baseline
  committed (`tests/perf/baselines/perf-baseline-2026-06-15.md`); scheduled `perf` CI
  workflow (`.github/workflows/perf.yml`).
- **Deferred (documented — L008):** P12.09 daemon idle-RAM / dream-cycle cost; a
  run-over-run perf-regression detector (the benchmarks assert absolute NFR thresholds,
  which is the regression guard).

Exit checklist: integration suite <3s; perf suite asserts NFRs; 671 tests + 3 benchmarks,
ruff + compileall clean, clean Docker + CI.

## Phase 11 — Channels, OpenClaw, Extensions: COMPLETE (2026-06-24)

The final v2 ecosystem layer, delivered as one reviewable PR per slice (owner-merged).
Decision context: **Path A** (continue local-first forge-os); the dropped-in "Aegis
Lifecycle" enterprise roadmap was reconciled and **deferred to a future Path B** (a
separate `aegis` service that *embeds* `forge_os`, never folds into the core) — see
`plan/Phase-by-Phase System Upgrade and Sprint Planning/AEGIS-VS-FORGEOS-GAP-ANALYSIS.md`
and `ADDITIVE-BACKLOG.md`. Hard owner constraint honored throughout: **never mutate the
core** (`core/` + canonical `schemas/{config,state,security}.py` untouched); new capability
entered only via additive files, new Phase-11 schemas, and the adapter registry.

- **S1 — Extensions/plugins (PR #29, FR-EXT-001..004):** `schemas/extension.py`,
  `extensions/{manifest,store,installer,errors}.py`, `use_cases/extensions.py`,
  `cli/commands/plug.py` — `forge plug list/install/remove`. Permission validation is
  fail-closed (install rejected unless the SecurityEnforcer returns ALLOWED); unsigned
  extensions are audited; conflict→permission→signing order enforced.
- **S2a — Channels read path (PR #30, FR-CH-001/002/003, FR-SEC-005):** `schemas/channel.py`,
  `channels/{base,console,normalize,errors}.py` (`ChannelAdapter` Protocol + `BaseChannelAdapter`),
  `use_cases/channels.py`, `cli/commands/channel.py` — `forge channel status/broadcast`.
  Status query is byte-for-byte read-only (regression-guarded).
- **S2b — Channels write path (PR #31, FR-CH-004/005, P11.05/07):** identity binding
  (`channels/identity.py`, one-time pairing, refuse-rebind), default-deny channel action
  policy (`channels/policy.py`, only `status`/`feedback` allowed unbound), feedback intake
  with dedup + rate-limit (`channels/intake.py`) — `forge channel feedback/pair/confirm`.
- **S3 — OpenClaw adapter (PR #33, FR-OCA-001..006):** `schemas/openclaw.py`,
  `adapters/openclaw/{adapter,channel}.py` — optional `OpenClawAdapter(IKernelAdapter)` on the
  Phase 08 ACP foundation (reuses `ACPClient` session list/resume/close + `session/update`
  streaming), persona→SOUL/IDENTITY/system-prompt, SecurityEnforcer-gated default-deny tool
  policy, webhook→Forge-event bridge, memory-separation guard (canonicalized; refuses
  protected/absolute/tree-escaping targets), offline fallback (unreachable → normalized
  `AGENT_FAILED`, state untouched). Interface + documented placeholders + mock tests only —
  no OpenClaw wire protocol invented (HTTP/WS transport deferred to P11.08). Registered behind
  a `gateway_command` guard; surfaced via the existing `AdapterUseCases.status` path.

Each slice: SRS-traced `tasks/todo.md` gate, layer gates clean (domain↛cli; schemas pure),
core-untouched verified, adversarially reviewed (Workflow + JSON schema, per-finding
verification — S3 fixed 9 confirmed findings incl. the `is_protected_path` canonicalization in
L009), and Docker-validated. **794 tests pass** (host `.venv` + clean `python:3.12-slim`),
ruff + compileall clean.

## CLI + Observability Backlog (post-Phase-11): COMPLETE (2026-06-24)

A scoped backlog after Phase 11, planned in PR #35 (two trace-verified scope docs) and delivered
as one owner-merged PR per slice. Hard constraint honored: **never mutate the core** (`core/` +
canonical `schemas/{config,state,security}.py` untouched); each entered via additive files + one
`app.add_typer` line. Every slice was adversarially reviewed (Workflow + JSON schema, per-finding
verification) and host + clean `python:3.12-slim` Docker validated.

- **`forge doctor` (PR #36, NEW FR-HD-006, SRS 4.1→4.2):** environment/install preflight
  (`schemas/doctor.py`, `health/doctor.py::EnvironmentDoctor`, `use_cases/doctor.py`,
  `cli/commands/doctor.py`) — distinct from FR-HD-001 project health; reuses
  `AdapterUseCases.status()`. Docker-first caught a host-masked dep bug (`click` is no longer a Typer
  dep) → **L010**.
- **`forge health knowledge` (PR #37, FR-HD-002):** surfaces the orphaned `KnowledgeUseCases`
  (integrity scans + artifact token-budget) on `health_app`; review fixed a raw-traceback/path-leak
  on a corrupt store (caught the stores' shared `RuntimeError` base).
- **Per-session token monitor (PR #38, FR-HD-003 + FR-TE-003):** `context/token_monitor.py` pure
  evaluator + a `TokenBudgetExceeded` event, wired into the sync *and* async spawn paths
  (best-effort; never breaks a spawn). Review caught a dual-`ConfigError` spawn-break → **L011**.
- **F0 — adapter event recording (PR #39, enables FR-TE-001):** `bind_event_store` seam on
  `BaseKernelAdapter` + `create_adapter_from_config(*, event_store=...)`; the sync `run_stage_agent`
  now binds the project Event Store so a real `forge agent run` records spawn cost/usage events
  (previously recorded only in tests). Only `ClaudeCodeAdapter` records; the async path
  (`AsyncDummyAdapter`) is out of scope by design.
- **`forge cost` (PR #40, FR-TE-001/004, FR-COST-002):** read-only token/$ aggregation by stage
  (`schemas/cost.py`, `use_cases/cost.py`, `cli/commands/cost.py`), joining
  `AdapterSpawnStarted`→`Completed` by `run_id`. Honest: source-adapter labeled, `None` cost shown
  as "no pricing" (never faked 0), shadow/canary + Dreamer streams reported "no data source yet".
  Review hardened the untrusted-`events.db` read path (9 fixes: malformed-JSON/non-dict/non-string
  rows degrade instead of crashing; no read-only DB creation; consistent rounding).

Gated/build-later (no work without owner go): **`forge doctor --fix`** (NEW FR-HD-007, needs an SRS
bump), the **always-on daemon monitor** (FR-HD-003/005, FR-COST-004), and **OTLP tracing**
(FR-OBS-001, FR-SEM-002, optional dep). See `tasks/todo.md` and `plan/SCOPE-observability-cost-backlog.md`.

**893 tests pass** (host `.venv` + clean `python:3.12-slim` Docker), ruff + compileall clean.

## Active Work: Phase 05.5 (kernel-first, D5=B)

Per D5=B (open-source kernel-first sequencing), tactical work resumed on the **kernel adapter layer** ahead of Phase 10. Landed (2026-06-08, PRs #1 + #2):

- `kernel/types.py` — canonical adapter contract (EventKind, NormalizedEvent, ToolUseProposal, ToolResult, AgentPersona, KernelCapabilities, IKernelAdapter)
- 5 new adapters: `human`, `claude_raw`, `claude_sdk`, `codex`, `opencode` (all implementing `IKernelAdapter`, async-generator + proposal-boundary)
- `adapters/bridge.py` — `AsyncToSyncBridge` (IKernelAdapter → sync `KernelAdapter` Protocol)
- `adapters/registry.py` — all 6 adapters registered with optional-dep guards
- `harness/comparison_harness.py` — multi-kernel benchmark harness
- Full test coverage: every adapter module now has a test file (rule #5). 371 tests total.
- L006 captured: validate in Docker with latest deps before claiming green.

**ClaudeCodeAdapter Slice 2 — landed 2026-06-09 (P055.06-08):** hook lifecycle (`adapters/claude_code/hooks.py::ClaudeSettingsHookWriter`) + event-store recording (`AdapterSpawnStarted` → N×`AdapterStreamEvent` → `AdapterSpawnCompleted`/`AdapterSpawnFailed` under a per-spawn `run_id`; `run_id` exposed on `AgentHandle.metadata`). 395 tests (host + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean.

**Task-ID collision resolved:** the multi-adapter expansion commit (`deb4bec`) was loosely labelled "P055.06-12"; that label is informal. The phase-doc deliverables table is the single source of truth — P055.06-08 are Slice 2 (just landed), P055.09-15 remain ClaudeCodeAdapter Slices 3-6.

**ClaudeCodeAdapter Slice 4 — landed 2026-06-09 (P055.11-12):** made `claude_code` actually selectable — fixed the broken `_claude_code_factory` (was passing an unsupported `model=`, no binary check) to do `shutil.which("claude")` + pass `claude_bin`/`model`; threaded `--model` support end-to-end; added `forge adapter status` (`use_cases/adapters.py` probes each adapter → enabled/default/available/reason/capabilities). Config-driven selection stays **fail-loud** (no silent dummy fallback). CI now live (`.github/workflows/ci.yml`, mirrors the Docker gate). 439 tests (host + Docker + GitHub CI), ruff/compileall clean. Manual smoke: `forge adapter status` shows `claude_code` available when the binary is on PATH.

**ClaudeCodeAdapter Slice 1.5 — real-contract reconciliation, 2026-06-09:** a de-risk check against the real `claude` v2.1.169 found Slices 1–3 were built on a *fabricated* stream-json schema (the phase doc guessed `{"type":"text",...}`; reality is `system`/`assistant`/`user`/`result` envelopes) plus wrong flags (`--max-turns` doesn't exist; `--verbose` is required). Rewrote `runner.py` (flags + parser), dropped `max_turns`, now record real token usage/cost, committed a gold capture (`tests/fixtures/claude_code/real_text_run.jsonl`) with a test that parses it. Captured as **L007**. 427 tests, ruff/compileall clean.

**ClaudeCodeAdapter Slice 3 — landed 2026-06-09 (P055.09-10):** `adapters/claude_code/replay.py` — `ClaudeCodeAdapter.replay_session(run_id)` reconstructs the `AgentHandle` by re-projecting the recorded `AdapterSpawnStarted`/`AdapterStreamEvent`/`AdapterSpawnCompleted` stream **without** invoking the subprocess (FR-ES-003 / FR-ES-004 / ADR-005); `ReplayError` for missing/incomplete/failed runs. Slice 2's completed event now records `handle_id` so replay restores the exact handle. 417 tests (host + clean `python:3.12-slim` Docker, latest deps), ruff clean, compileall clean.

**ClaudeCodeAdapter Slice 5 — landed 2026-06-10 (P055.13-14):** SecurityEnforcer pre-spawn gate — `ClaudeCodeAdapter` accepts an optional `security_enforcer` (DI, same pattern as `event_store`/`hook_command`); `spawn_agent` validates `execute_command`/`shell` against the security profile *before* the hook context and subprocess. DENIED → `ClaudeCodeSpawnError` + terminal `AdapterSpawnFailed` event; the enforcer writes the audit entry to `.forge/security-audit.jsonl` (authoritative for security decisions; event store records lifecycle only). Gate is **fail-closed**: an enforcer exception aborts the spawn — it never proceeds unaudited. 447 tests (host + clean `python:3.12-slim` Docker, latest deps + GitHub CI), ruff/compileall clean.

**ClaudeCodeAdapter Slice 6 — landed 2026-06-10 (P055.15):** `forge init --adapter claude-code [--permission-mode <mode>]` — verifies the binary up front (`runner.get_claude_version()`, fail-early before any file is written) and scaffolds with `default_adapter: claude_code` enabled (exactly one default enabled; dummy disabled when not chosen). `--permission-mode` (choices captured from real claude 2.1.170 `--help`, gold contract-set test guards drift) threads config → factory → adapter → `claude --permission-mode`. Single validation authority `runner.validate_permission_mode()` shared by adapter and CLI. Manual smoke: generated config selects `ClaudeCodeAdapter(permission_mode="plan")` via `create_adapter_from_config`. 471 tests (host + clean `python:3.12-slim` Docker + GitHub CI), ruff/compileall clean.

**Kill criterion PASSED — 2026-06-10.** Real `forge agent run --stage srs` with `default_adapter: claude_code` end-to-end: persona → claude subprocess (haiku, 6 tool uses, 73s, $0.08) → agent-written `SRS.md` → contract passed → outputs registered → run record persisted. The run exposed three integration bugs DummyAdapter had masked, all fixed: (1) `extract_text_outputs` emitted `OutputArtifact(path="")` which the ArtifactRegistry rejects — replaced by `extract_outputs(result, project_root)` deriving file artifacts from Write/Edit/NotebookEdit tool uses (transcript text → `metadata["final_text"]`); (2) `_stage_context` omitted the contract's `required_outputs` (+ now signals `execution_mode: "batch"`); (3) `claude -p` defaulted to conversation — `_build_prompt` appends a batch execution directive. 476 tests (host + Docker + CI), ruff/compileall clean.

**Phase 05.5 COMPLETE.** Next milestone: open-source launch prep per D5 (Apache-2.0 LICENSE + README rewrite). Phase 10 (Daemon/Dreamer/lazy context) stays paused pending `/STATUS.md` D4/D3 owner decisions.

## Next Phase

- Phase: 13 (Documentation & Release Engineering) — the last remaining roadmap phase.
- File: `plan/PHASE-13-docs-release-engineering.md`
- Status: **not started** — owner go/no-go recommended (Fork B; outward-facing release surface).
  Phases 00–12 are now complete; only Phase 13 and the conditional Fork-A `A1` (commitgate
  extract) remain in the index.

## Last Completed Phase

- Phase: 11 (Channels, OpenClaw, extension/plugin system)
- File: `plan/PHASE-11-channels-openclaw-extensions.md`
- Status: complete (2026-06-24) — S1 extensions (#29), S2a/S2b channels (#30/#31), S3 OpenClaw
  (#33). OpenClaw shipped as interface + documented placeholders + mock tests (HTTP/WS transport
  deferred to P11.08); core untouched throughout.

## Discipline & Clean Code Enforcement (Phase 08+)

Before implementing any task, run:
```bash
git log --oneline -5
git diff HEAD
git status
cat plan/RESUME.md 2>/dev/null || echo "No resume needed"
```

All Phase 08+ implementations MUST follow:

| Rule | How to Verify |
|------|--------------|
| **CLI never imports domain directly** | `grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/` — **zero matches required** |
| **No upward imports from domain** | `grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/kernel/` — **zero matches required** |
| **Schemas are pure data** | `grep -rn "from forge_os" src/forge_os/schemas/ --include="*.py"` — **only stdlib/pydantic imports allowed** |
| **Every use case has tests** | `ls tests/test_use_cases_*.py` — must exist for each `src/forge_os/use_cases/*.py` |

Last validation commands:

- `.venv/bin/python -m pytest` — 67 passed.
- `.venv/bin/python -m ruff check src tests` — passed.
- `.venv/bin/python -m compileall src tests` — passed.

Expected test count after Phase 08: 120+ passed.

## Resolved Decisions

1. Runtime: Python 3.11+.
2. Package import name: `forge_os`.
3. Preferred CLI command: `forge`.
4. Development package manager preference: `uv`, while preserving standard `pip` compatibility.
5. Distribution: local Python package first, `pipx` when ready, standalone binary later.
6. Adapter priority:
   1. `DummyAdapter`
   2. `ClaudeCodeAdapter`
   3. `CodexAdapter`
   4. `OpenClawAdapter`
   5. `OpenCodeAdapter`
   6. `LocalLLMAdapter`
   7. `HumanAdapter`
7. OpenClawAdapter architecture: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
8. Core state ownership: Forge OS core is the sole writer of canonical state.
9. Open formats: YAML, JSON, JSON Lines, Markdown, and GraphML.
10. Security baseline: least privilege, human approval for high-risk/destructive actions, explicit timeouts for executable checks.
11. ACP Protocol: JSON-RPC 2.0 over newline-delimited JSON on stdio.
12. ACP Registry: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
13. ACP session features (list, resume, close) are stabilized as of April 2026.
14. ACP agents must be registered in the official ACP Registry at `github.com/agentclientprotocol/registry`.
15. ACP integration is additive — existing LiteLLMAdapter behavior is preserved.
16. ACP agent installation supports: binary archives, npx packages, and uvx packages per manifest.
17. ACP agents spawned by Forge OS must respect SecurityEnforcer policies.
18. Phase 01 CLI scaffold is complete with `forge init`, `forge status`, `forge config show`, `forge config validate`, and `forge explain`.
19. Phase 02 state machine is complete with `forge stage list/start/complete/advance/override`, atomic writes, transition validation, state markdown sync, and transition event logging.
20. Phase 03 events/hooks are complete with normalized lifecycle events, in-process event bus, hook registry, hook timeout/failure isolation, and `forge events list/tail`.
21. Phase 04 gates MVP is complete with file/pattern gates, severity handling, gate reports, `forge gate list/check/report`, gate events, persisted latest results, and stage advancement enforcement.
22. Phase 05 adapters/agents are complete with KernelAdapter interface, adapter registry/config placeholders, DummyAdapter, 12 stage personas, 4 cross-stage personas, output contracts, agent execution logs, `forge adapter list`, `forge agent list/contracts/run`, and optional `forge stage start --spawn-agent`.
23. Phase 06 memory/lessons are complete with YAML lesson store, reflection files, lesson add/list/approve/deprecate CLI, reflection list/show CLI, stage-completion reflection capture, pending lesson extraction queue, and approved high-confidence lesson injection into agent context.
24. Phase 07 ADG/context is complete with artifact registry, JSON ADG persistence, stale downstream propagation, deterministic spread-activation context pruning, context selection audit logs, artifact/context CLI commands, stale artifact display in `forge status`, and pruned context integration for agent spawns.
25. **Phase 08 CLI refactoring complete** — all Phase 08+ commands moved to `src/forge_os/cli/commands/` sub-modules (`backtrack.py`, `security.py`, `health.py`, `acp.py`). `main.py` slimmed from 1240→895 lines. Separation of concerns enforced for all future commands.

## Blocking Questions

None currently.

## Phase 09 Task Summary

### Health Checks
| ID | Task | Status |
|---|---|---|
| P09.01 | Implement `forge health check` | 🔄 |
| P09.02 | Add hook unit test harness | 🔄 |
| P09.03 | Add gate simulation fixtures | 🔄 |
| P09.04 | Knowledge integrity scanner | 🔄 |
| P09.05 | Token budget report | 🔄 |

### Global Memory
| ID | Task | Status |
|---|---|---|
| P09.06 | Global memory directory under `~/.forge/` | 🔄 |
| P09.07 | Global lesson promotion with approval | 🔄 |
| P09.08 | Project profiles memory | 🔄 |
| P09.09 | Pattern tracker | 🔄 |

### Skill Mining
| ID | Task | Status |
|---|---|---|
| P09.10 | Skill proposal command | 🔄 |
| P09.11 | Skill approval workflow | 🔄 |
| P09.12 | Skill install/use commands | 🔄 |

### ACP Agent Health
| ID | Task | Status |
|---|---|---|
| P09.13 | ACP agent health checks using session/list | 🔄 |
| P09.14 | Agent restart/recovery logic | 🔄 |
| P09.15 | Session health monitoring | 🔄 |

### Phase 09 Validation
| Item | Target |
|---|---|
| Tests pass | TBD (186 baseline) |
| Ruff lint | clean |
| Compileall | clean |

## Notes For The Next Implementer

Read:

1. `BUILD_SPEC.md`
2. `plan/ORCHESTRATOR.md`
3. `plan/PHASE-08.5-async-cocoindex.md` — current phase plan
4. `plan/PHASE-08-backtrack-security.md` — completed phase for reference
5. `plan/PHASE-07-adg-context.md`
6. `plan/PHASE-05-adapters-agents.md`
7. `plan/v4/KERNEL_UPDATED_PLAN.md` — async research, ACP registry details
8. `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — CocoIndex evaluation details
9. `plan/KERNEL_ADAPTER_INTERFACE.md`
10. `plan/ADAPTER_ROADMAP.md`
11. `ARCHITECTURE.md`
12. `SCHEMAS.md`
13. Existing source under `src/forge_os/`
14. Existing tests under `tests/`

### Phase 08.5 Completed Deliverables

| Workstream | Deliverable | Status |
|---|---|---|
| **A: Async Migration** | AsyncKernelAdapter protocol, AsyncDummyAdapter, async executor, HTTP client | ✅ |
| **B: Incremental Cache** | Lightweight mtime+content cache replacing CocoIndex (zero deps) | ✅ |
| **C: Event Store** | SQLite append-only log, dual-write, replay, snapshots, Phase 08 events | ✅ |

### Deferred Items

- LiteLLMAdapter ACP integration + fallback chain — deferred to async migration cleanup
- Full event-sourced state migration — deferred to later phases
- Task ID numbering divergence: CURRENT_PHASE.md renumbered P08.5.x for brevity

### Clean Code Rules (Continuing)

All new Phase 09+ commands MUST live in their own file under `src/forge_os/cli/commands/<domain>.py`.
Each file exposes a Typer sub-app. Register with `app.add_typer()` in `main.py`.
Business logic belongs in `use_cases/`, not in CLI command files.

### Directory Structure (Phase 09)

```
src/forge_os/
├── adapters/
│   ├── async_base.py        # AsyncKernelAdapter protocol (Phase 08.5)
│   ├── async_dummy.py       # AsyncDummyAdapter (Phase 08.5)
│   ├── base.py              # Sync KernelAdapter protocol (preserved)
│   └── dummy.py             # Sync DummyAdapter (preserved)
├── agents/
│   └── executor.py          # run_stage_agent_async added (Phase 08.5)
├── context/
│   ├── pruner.py            # mtime cache added (Phase 08.5)
├── events/
│   ├── store.py             # Event Store for dual-write (Phase 08.5)
│   └── model.py             # Phase 08 event types registered
├── kernel/
│   ├── acp_client.py        # Phase 08
│   ├── acp_registry_adapter.py  # Phase 08
│   └── http.py              # Async HTTP client (Phase 08.5)
└── cli/commands/
    ├── backtrack.py          # Phase 08
    ├── security.py           # Phase 08
    ├── health.py             # Phase 09 scaffold
    └── acp.py               # Phase 08
```

Last validation commands:

- `.venv/bin/python -m pytest` — 186 passed (67 baseline + 66 Phase 08 + 20 async + 29 Event Store + 4 cache).
- `.venv/bin/python -m ruff check src tests` — clean.
- `.venv/bin/python -m compileall src tests` — passed.

Phase 08.5 complete ✅. All three workstreams delivered. Moving to Phase 09.