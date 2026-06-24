# Scope — `forge doctor` + `forge health knowledge` (token-budget surface)

> **Status:** proposed (awaiting owner go/no-go). Two small, additive CLI features.
> **Constraint:** never mutate the core; strict layers (cli → use_cases → domain → schemas).
> **Discipline:** SRS-driven (new requirement → SRS version bump + changelog row *before* impl),
> 4-question task gate, one logical change per PR, owner-merge only.

---

## Why

Two observability gaps surfaced while auditing health/token monitoring:

1. **No environment preflight.** `forge health check` inspects *project state* (state/gates/adg/
   memory/acp checkers) and requires a project. Nothing answers "is my *machine/install* able to
   run Forge?" — the `brew doctor` / `flutter doctor` role (Python version, venv, deps, adapter
   binaries, config validity, write access).
2. **`report_token_budget()` is orphaned.** `KnowledgeUseCases.report_token_budget()`
   (`use_cases/knowledge.py:57`) computes a real token-budget aggregate but is wired into **no CLI
   command and not even into `forge health check`** — it's dead from a user's perspective.

---

## SRS impact

| Feature | SRS trace | New requirement? |
|---------|-----------|------------------|
| A. `forge doctor` | **NEW FR-HD-006** (§3.8 Health & Sustainability Daemon) | Yes → SRS **4.1 → 4.2** + changelog row |
| B. `forge health knowledge` | **existing FR-HD-002** "Knowledge Integrity Checks" — the integrity scans are an exact fit; the artifact token-budget aggregate rides along as a supplementary panel | No — no version bump |

> **Design-review correction (2026-06-24):** an adversarial review of an earlier draft caught a
> **false SRS trace** — Feature B was traced to FR-HD-003 ("Token Budget Monitor — measures
> *injected-context token count per session* and warns on overage"), but
> `report_token_budget()` is a *project-wide artifact aggregate* with no session, no
> injected-context measurement, and no overage warning. That draft also misquoted FR-HD-003's
> acceptance. Corrected here: Feature B traces to **FR-HD-002** (which `KnowledgeUseCases` genuinely
> implements). The real FR-HD-003 per-session monitor is **net-new** work — see Non-goals.

**Proposed FR-HD-006 (drafted, for approval):**

> **FR-HD-006 | Environment Preflight Diagnostic** — `forge doctor` verifies the host environment
> can run Forge: Python runtime version, active virtualenv, and required dependencies (all
> **install-level**, run always); and — **when inside a project** — adapter availability (reusing
> the adapter-status probe), `.forge/` presence, `config.yaml` validity, and write access. Reports
> pass/warn/fail per check with a remediation hint; runnable **with or without** a project (the
> project-scoped checks degrade to INFO "skipped — not in a Forge project").
> **Acceptance:** exits 0 on a healthy install; non-zero with an actionable remedy when a required
> install-level check fails; runs outside a project with project-scoped checks reported as skipped.

**Proposed changelog row (SRS v4.2):**

> `| 4.2 | 2026-06-24 | tonmoy | Added FR-HD-006 (Environment Preflight Diagnostic, forge doctor). Surfaced existing FR-HD-002 knowledge-integrity + artifact-budget reporting via CLI (forge health knowledge). |`

`forge doctor` is deliberately **distinct** from FR-HD-001 (`forge health check`): doctor =
install/environment preflight (no project required); health check = project subsystem-state
integrity (project required).

---

## Feature A — `forge doctor`

A single read-only preflight command. Each check yields pass / warn / fail + a remedy; the command
exits non-zero iff any check **fails** (warns are non-fatal), so it is scriptable in CI/setup.

**Install-level checks — always run (no project required):**

| Check | Fail/warn rule | Reuses | Remedy on failure |
|-------|----------------|--------|-------------------|
| Python runtime | **fail** if `< 3.11` | `sys.version_info` (pyproject `requires-python>=3.11`) | "Use Python 3.11+" |
| Virtualenv | **warn** if not in a venv | `sys.prefix != sys.base_prefix` | "Activate `.venv`" |
| `forge_os` install | **fail** if not importable | `importlib.metadata.version` | "`pip install -e .`" |
| Core deps | **fail** if pydantic/typer/click/pyyaml missing | import probe | "`pip install -e .[dev]`" |

**Project-scoped checks — run only inside a project; else INFO "skipped — not in a Forge project":**

| Check | Fail/warn rule | Reuses | Remedy on failure |
|-------|----------------|--------|-------------------|
| In a project? | **info** if no `.forge/` (drives the gating below) | `project_root` resolution (best-effort; no raise) | "`forge init`" |
| Adapter availability | **info** — lists available/unavailable + reason | **`AdapterUseCases.status()`** (no re-probe) | per-adapter reason already supplied |
| Config validity | **fail** if `load_config` raises | **`config.loader.load_config`** | "fix `config.yaml`" |
| `.forge/` writable | **fail** if not writable | write probe | "check permissions" |

> **Why adapter availability is project-scoped (review fix):** `AdapterUseCases.status()` reads
> `.forge/config.yaml` (it answers "which adapters are selectable for *this project's* config") and
> raises `ConfigError` with no project. So it is only valid inside a project; outside one, the whole
> project block — adapter / config / writable — reports a single INFO "skipped — not in a Forge
> project". We deliberately do **not** drop to the lower-level `AdapterRegistry` probe to force a
> config-independent binary check: that would be re-probing (violates reuse) and YAGNI for v1.

**Files (all additive except one `main.py` line):**
- NEW `schemas/doctor.py` — `DoctorStatus(StrEnum){PASS,WARN,FAIL,INFO}`, `DoctorCheck(name, status,
  detail, remedy: str|None)`, `DoctorReport(checks, ok, counts)`. Pure pydantic.
- NEW `health/doctor.py` — `EnvironmentDoctor(project_root: Path | None)`: env/install/deps/fs
  checks as small functions returning `DoctorCheck`. Injectable `project_root`; unit-testable via
  `monkeypatch` (python version, venv, perms).
- NEW `use_cases/doctor.py` — `DoctorUseCases(project_root: Path | None).run() -> DoctorReport`.
  **Best-effort project resolution:** detect whether `project_root` (or cwd) is a Forge project; if
  not, emit the install-level checks plus a single INFO "skipped — not in a Forge project" for the
  project block (it does **not** call `AdapterUseCases`/`load_config` at all when there is no
  project). Inside a project it composes `EnvironmentDoctor` + **reuses** `AdapterUseCases.status()`
  and `load_config`. Catches domain exceptions → report (never raises out).
- NEW `cli/commands/doctor.py` — `doctor_app`; `forge doctor [--json]`; renders icons + exit code.
- MODIFY `cli/main.py` — one line: `app.add_typer(doctor_app, name="doctor")`.
- TESTS — `tests/test_health_doctor.py` (env checks, monkeypatched), `tests/test_use_cases_doctor.py`
  (composition + adapter-status reuse mocked, in/out of project via `tmp_path`),
  `tests/test_cli_doctor.py` (`CliRunner`: exit 0 healthy / exit 1 on injected fail / `--json`).

**4-question gate:**
1. *SRS:* FR-HD-006 (new).
2. *Files:* above (additive + 1 `main.py` line).
3. *Verify:* `test_cli_doctor` exit-code matrix; monkeypatched fail/warn cases; **a no-project test
   asserting the project block (adapter/config/writable) degrades to a single INFO and never
   raises**; manual `forge doctor` smoke inside and outside a project.
4. *What breaks:* nothing existing — new top-level command; inside a project it reuses
   already-tested `AdapterUseCases`/`load_config`, outside one it must not call them (review fix).
   Risk: env introspection (venv/perms) is host-dependent → guard with injection + monkeypatch so
   tests stay deterministic (L001-style isolation).

---

## Feature B — `forge health knowledge`

Surface the **entire** orphaned `KnowledgeUseCases` (all three methods are currently CLI-invisible)
on the **existing** `health_app` sub-app (cohesive; no new `add_typer`). One command, two panels:

- **Integrity panel → FR-HD-002 (exact fit):** `scan_lesson_references()` (stale artifact
  references) + `scan_lesson_conflicts()` (duplicate/conflicting lessons). FR-HD-002 reads "Scans
  LKG for conflicts … stale references. Results in health dashboard" — these scans *are* that.
- **Artifact-budget panel (the user's ask):** `report_token_budget()` — the project-wide artifact
  token aggregate (fresh/stale counts + token sums + avg), labeled honestly as the **artifact token
  footprint**. It is supplementary context, **not** claimed to satisfy the FR-HD-003 per-session
  monitor (see Non-goals).

**Files:**
- MODIFY `cli/commands/health.py` — add `@health_app.command("knowledge")` → calls
  `KnowledgeUseCases(root)` for both panels; renders integrity issues + the artifact-budget
  aggregate; `--json` for scripts. Exit non-zero if integrity issues are found (scriptable).
- TESTS — `tests/test_cli_health_knowledge.py` (integrity panel finds a seeded stale ref /
  duplicate; artifact-budget aggregate renders; `--json` shape; exit code). Extend
  `tests/test_use_cases_knowledge.py` only if a case is missing.

**4-question gate:**
1. *SRS:* **FR-HD-002** (existing — the integrity scans implement it; the command surfaces it).
   Honest trace — no fabricated acceptance, no version bump.
2. *Files:* above.
3. *Verify:* CLI test on a `tmp_path` project with a seeded stale reference + duplicate lesson +
   artifacts → asserts integrity findings, the rendered budget fields, `--json`, and exit code.
4. *What breaks:* nothing — additive subcommand on an existing sub-app; the use case already exists.

---

## Non-goals (YAGNI — explicitly out of scope)

- **No real FR-HD-003 per-session monitor** — measuring *injected-context* token count *per agent
  session* and *warning on overage* is net-new behavior (it does not exist in
  `report_token_budget()`). If wanted, it's a separate item against FR-HD-003, not a CLI surface
  over the artifact aggregate. Flagged for owner consideration; out of scope here.
- **No `forge cost` $-spend dashboard** (FR-COST-002 / FR-TE-001 production-vs-evolution spend) — a
  separate, larger feature; this scope is token *budget* (context size), not provider *cost*.
- **No OTLP / dual-stream tracing** (FR-OBS) — unrelated.
- **No auto-remediation** — doctor reports + suggests; it never mutates the environment.
- **No new daemon task / always-on monitor** — both features are on-demand CLI only.
- **Reuse, don't reinvent:** doctor calls `AdapterUseCases.status()` and `load_config`; it does not
  re-implement binary/config probing.

---

## Execution plan (owner-merge per PR)

| PR | Content | SRS |
|----|---------|-----|
| **PR-1** | SRS bump 4.1→4.2 (changelog row + FR-HD-006) **+** `forge doctor` (schema/domain/use-case/CLI/tests) | FR-HD-006 |
| **PR-2** | `forge health knowledge` (integrity + artifact-budget CLI surface + tests) | FR-HD-002 |

Each: SRS-traced `tasks/todo.md` gate, layer gates clean (domain↛cli, schemas pure), adversarial
review (Workflow + JSON schema), host + clean `python:3.12-slim` Docker validation, one reviewable
PR for owner merge. The SRS changelog row lands in PR-1 **before** the FR-HD-006 implementation in
the same PR (doc edit first commit).

**Estimate:** small — PR-1 ≈ 250–350 lines incl. tests; PR-2 ≈ 80–120 lines. ~2 PRs.
