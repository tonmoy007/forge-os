# Forge OS — Captured Lessons

> **Purpose:** Every time the user corrects a mistake, the lesson is recorded here BEFORE fixing the code.
> The lesson is more valuable than the fix because it prevents future repetitions.

## How to Use

1. User gives a correction.
2. **First:** Add an entry to this file with date, trigger, root cause, and rule.
3. **Second:** Fix the code.
4. **Third:** Reference the lesson ID in the commit message.

## Lessons

### L001 — Global state in ~/.forge/ breaks test isolation
- **Date:** 2026-05-12
- **Trigger:** Tests failing because `GlobalLessonStore`, `ProjectProfileStore`, and `SkillUseCases` wrote to real `~/.forge/` directory, causing cross-test pollution and leftover state from prior runs.
- **Root cause:** Used `Path.home()` as default path without injection mechanism. Tests shared mutable global state.
- **Rule:** All modules that persist to `~/.forge/` MUST accept an optional `forge_dir: Path | None = None` parameter. When `None`, default to `Path.home() / ".forge"`. Tests MUST pass `tmp_path`-based directories.
- **Files affected:** `memory/global_store.py`, `memory/project_profiles.py`, `use_cases/skills.py`, `tests/test_health_phase09.py`

### L002 — Ruff `E741` blocks single-letter variable names in comprehensions
- **Date:** 2026-05-12
- **Trigger:** `ruff check` failing with `E741 ambiguous variable name: 'l'` on list comprehensions using `for l in ...`.
- **Root cause:** The `l` variable name is visually ambiguous with `1`. Ruff's `E741` rule rejects it even in throwaway comprehension variables.
- **Rule:** Use `le` (for lesson elements), `a` (for artifacts), or other unambiguous short names in comprehensions. Never use `l`, `O`, or `I` as variable names.

### L003 — SQLite WAL mode + synchronous=NORMAL is ideal for local-first CLI tools
- **Date:** 2026-05-12
- **Trigger:** Designing the Event Store for Forge OS required choosing SQLite settings that balance durability with performance for a developer-local tool.
- **Root cause:** Default SQLite settings favor maximum durability (full fsync on every write) at the cost of throughput. For a local dev tool, the last few ms of durability can be traded for performance.
- **Rule:** For local-first CLI tools using SQLite, always enable `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. WAL allows concurrent reads during writes. NORMAL trades the last few ms of fsync for throughput — acceptable for non-critical local data.

### L004 — CocoIndex requires PostgreSQL, making it unsuitable for local-first tools
- **Date:** 2026-05-12
- **Trigger:** Evaluating CocoIndex as incremental indexing engine for Context Pruner.
- **Root cause:** CocoIndex requires PostgreSQL for its metadata store. This is a hard dependency that conflicts with Forge OS's "local-first, zero-infrastructure" design principle.
- **Rule:** Before adopting any external dependency for a local-first CLI tool, verify it doesn't require a database server, network service, or cloud API. CocoIndex is suitable for server-side deployments only. For local incremental processing, use `st_mtime` caching instead.

### L005 — Inject `forge_dir` rather than hardcoding `Path.home()` in global modules
- **Date:** 2026-05-12
- **Trigger:** Multiple iterations needed to fix test isolation (a corollary to L001 with broader scope).
- **Root cause:** Several modules (`GlobalLessonStore`, `ProjectProfileStore`, `SkillUseCases`) referenced `Path.home() / ".forge"` directly, making them impossible to unit test in isolation.
- **Rule:** Any module that reads/writes to `~/.forge/` MUST accept the forge directory as a constructor parameter. The `Path.home()` default is acceptable only as a fallback when no explicit path is given. This enables both production use (no arg = ~/.forge) and test isolation (tmp_path injected).

### L006 — The host `.venv` masks dependency drift; Docker with latest deps is the real gate
- **Date:** 2026-06-08
- **Trigger:** Full suite was green on the host `.venv` (typer 0.25.1 / click 8.3.3) but 28 CLI tests failed in a fresh Docker `python:3.12-slim` run (`AttributeError: 'CliRunner' object has no attribute 'isolated_filesystem'`).
- **Root cause:** `pyproject.toml` pins ranges (`typer>=0.12,<1.0`), so the host venv resolved an older Typer while Docker installed Typer 0.26.7, which vendors a click that dropped the long-deprecated `CliRunner.isolated_filesystem`. The test suite depended on a third-party test helper that upstream removed. The stale host venv hid the breakage.
- **Rule:** Validate the suite in a clean Docker container with freshly-resolved latest deps BEFORE claiming "tests pass" or merging — never trust the host venv alone (it carries old resolved versions). Do not depend on deprecated third-party test helpers; own them. The fix here is `tests/cli_helpers.py::isolated_filesystem` (an owned `tempfile` + `chdir` context manager), not pinning Typer down to dodge the removal.
- **Files affected:** `tests/cli_helpers.py` (new), `tests/test_cli_phase01.py`, `tests/test_cli_stage_phase02.py`, `tests/test_cli_events_phase03.py`, `tests/test_cli_gates_phase04.py`, `tests/test_adapters_agents_phase05.py`, `tests/test_memory_phase06.py`, `tests/test_context_phase07.py`

### L007 — Verify an external tool's real contract before building an adapter on assumptions
- **Date:** 2026-06-09
- **Trigger:** A de-risk check before wiring `ClaudeCodeAdapter` into the CLI found that Slices 1–3 of the adapter were built against a **fabricated** `claude` stream-json schema. The phase doc had *guessed* `{"type":"text","content":...}` / `{"type":"tool_use",...}` / `{"type":"error",...}` top-level lines, plus flags `--max-turns` (doesn't exist in 2.1.x) and missing the **required** `--verbose`. Every mocked test passed because the mocks used the same wrong schema. Against the real `claude` v2.1.169 the adapter would error on unknown `--max-turns` or return an empty handle (real lines are `system`/`assistant`/`user`/`result` envelopes with text at `message.content[].text` and the final answer in the `result` line).
- **Root cause:** The adapter's I/O contract was taken from a plan document's *assumption*, never validated against the real binary; three slices and ~70 tests compounded on top of it. Mock-only tests cannot catch a wrong contract — they encode the same wrong assumption on both sides.
- **Rule:** Before building a parser/adapter over any external CLI/API, capture **one real sample** of its output (and confirm its flags via `--help`) and commit it as a gold-standard fixture. Add at least one test that runs the *real captured output* through the parser, not only synthetic fixtures. Verify the contract at the boundary **before** building layers on it — finding a wrong contract early (in isolated code) is far cheaper than after it's wired into the CLI, security, and replay.
- **Files affected:** `adapters/claude_code/runner.py` (flags + parser rewrite), `adapters/claude_code/adapter.py` (drop `max_turns`, record real usage/cost), `tests/fixtures/claude_code/real_text_run.jsonl` (new gold capture), `tests/test_adapters_claude_code.py` + `tests/test_adapters_claude_code_replay.py` (real-schema fixtures), `plan/PHASE-05.5-claude-code-adapter.md` (corrected contract).

### L009 — A path/membership guard over untrusted input must canonicalize before comparing — string matching is bypassable
- **Date:** 2026-06-24
- **Trigger:** Phase 11 S3 adversarial review (Workflow + schema) found the OpenClaw
  memory-separation guard `is_protected_path` did exact-string / prefix matching after only
  stripping a leading `./`. It returned False for `.forge/../.forge/state.json`, `.forge//state.json`,
  and `/abs/.forge/state.json`, so `sync_insights_back` *accepted* an insight targeting a
  protected source-of-truth file (FR-OCA-005). The mock tests passed because they encoded only the
  canonical spelling on both sides. The project's own `security.md` already says "reject `../`
  sequences, use allowlists" — the guard violated a standing rule.
- **Root cause:** Treated a security-relevant path check as a string-membership test instead of a
  path-equivalence test. `str.lstrip("./")` also silently mangled `.forge/...` → `forge/...` (it
  strips a *char set*, not a prefix), defeating even the canonical case until caught in build.
- **Rule:** Any guard that decides access/refusal from an untrusted path or identifier MUST
  canonicalize first: normalize separators, collapse `.`/`..` via `posixpath.normpath`, and reject
  absolute or tree-escaping forms (`startswith("/")`, `normpath` still containing `..`) before the
  membership/prefix check. Never use `lstrip`/`rstrip` to remove a *prefix*. Back fail-closed
  guards with regression tests for every evasion spelling (`..`, absolute, `//`, trailing space),
  not just the canonical one — mock-only tests that share the wrong assumption on both sides prove
  nothing (cf. L007).
- **Files affected:** `adapters/openclaw/adapter.py` (`canonical_relpath` + `is_protected_path` +
  `sync_insights_back`), `tests/test_adapters_openclaw.py`.

### L008 — Phase 12: guard perf NFRs with absolute-threshold benchmarks; defer process-RAM and run-over-run detection (documented gaps)
- **Date:** 2026-06-15
- **Trigger:** Phase 12 acceptance explicitly permits a written rationale (here) for any NFR target left unmeasured. Two P12 items were deferred rather than built out.
- **Root cause:** (1) NF-D-001/002 daemon idle-RAM + dream-cycle cost (P12.09) needs process-introspection tooling (psutil/`resource`) not otherwise required pre-1.0, and the daemon is optional and not yet run at scale. (2) A run-over-run perf regression detector (persist + diff benchmark JSON across runs) is operational infra whose value is marginal for a single-maintainer pre-1.0 project — the benchmarks already assert absolute NFR thresholds, which is the regression guard.
- **Rule:** Guard latency/throughput NFRs with benchmarks that assert the absolute SRS §5.1 thresholds (`tests/perf`, run by `.github/workflows/perf.yml`), not fragile run-over-run deltas. Re-open P12.09 (measure resident RAM) before making the daemon on-by-default; add a delta-vs-baseline detector only once multiple contributors or a CI perf-trend need exists.
- **Files affected:** `tests/perf/`, `tests/perf/baselines/perf-baseline-2026-06-15.md`, `.github/workflows/perf.yml`, `plan/CURRENT_PHASE.md`

### L010 — A dependency-readiness check must enumerate *declared* deps, not transitive/assumed ones; clean Docker is the only honest probe
- **Date:** 2026-06-24
- **Trigger:** `forge doctor` (FR-HD-006) passed on host `.venv` but failed in clean `python:3.12-slim` with `Core dependencies :: missing: click`. Typer 0.26.7 no longer declares `click` (`importlib.metadata.requires('typer')` lists none); the host venv had a stray `click` that masked a wrong assumption — a sharper instance of [[L006]].
- **Root cause:** `CORE_DEPENDENCIES` included `click` on the outdated belief that "typer bundles click". `click` is neither a forge-os nor a current-typer *declared* dependency, and its top-level import resolution varies by environment, so `importlib.util.find_spec("click")` is `None` on a clean install even though the CLI works.
- **Rule:** Any check that enumerates required packages MUST mirror the project's *declared* runtime dependencies in `pyproject.toml [project.dependencies]` (by import name: `pydantic`, `yaml`, `rich`, `typer`), never transitive or assumed packages. When adding such a check, validate it in a clean Docker image (no host-leaked packages) **before** sign-off — the host `.venv` accumulates transitive installs that produce false PASSes (cf. L006).
- **Files affected:** `src/forge_os/health/doctor.py` (`CORE_DEPENDENCIES`), `tests/test_health_doctor.py`.
