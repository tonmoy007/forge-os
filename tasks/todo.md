# tasks/todo.md — Phase 05.5 Slice 6: `forge init --adapter claude-code` bootstrap

> Slices 1–5 + 1.5 merged. CI live (PRs gated). This is Slice 6 — the final slice —
> per the phase-doc deliverables table (P055.15).

## Slice 6 — init bootstrap + `--permission-mode` (P055.15)

**SRS traceability:**
- **FR-KA-003** (Multiple Implementations — user switches kernels by config change): `forge init
  --adapter claude-code` writes `default_adapter: claude_code` + `enabled: true` so the project is
  born selecting the real kernel, with the binary verified up front (fail-early, no broken config).

### Tasks

- [x] **P055.15a** — `runner.py`: `get_claude_version()` (subprocess `claude --version`, raises
  `ClaudeCodeSpawnError` with install hint if missing/failing) + `CLAUDE_PERMISSION_MODES`
  (verified against claude 2.1.170 `--help`: acceptEdits, auto, bypassPermissions, default,
  dontAsk, plan) + `run_claude(permission_mode=...)` → `--permission-mode` flag.
- [x] **P055.15b** — `ClaudeCodeAdapter(permission_mode=...)` (validates against
  `CLAUDE_PERMISSION_MODES`, threads to `run_claude`); `_claude_code_factory` reads
  `permission_mode` from adapter config.
- [x] **P055.15c** — `scaffold.py`: `initialize_project(default_adapter=..., adapter_options=...)`
  validates against `ADAPTER_PRIORITY`, marks the chosen adapter `enabled: true`, merges options.
- [x] **P055.15d** — `cli/main.py init`: `--adapter` (kebab→snake normalize) + `--permission-mode`
  flags; claude-code path verifies the binary via `get_claude_version()` BEFORE scaffolding and
  prints the version; clean errors (exit 2) for unknown adapter / mode misuse, exit 1 for missing
  binary.

### Gate answers
1. **SRS:** FR-KA-003 (config-driven kernel switch at project birth).
2. **Files:** modify `adapters/claude_code/runner.py`, `adapters/claude_code/adapter.py`,
   `adapters/registry.py`, `project/scaffold.py`, `cli/main.py`; extend
   `tests/test_adapters_claude_code.py`, `tests/test_cli_phase01.py`.
3. **Verify:** 14 new tests (runner flag/version-check, adapter validation/threading, factory,
   6 CLI init paths); manual smoke with real claude 2.1.170: init writes config, bad adapter
   rejected, `create_adapter_from_config` on the generated config returns
   `ClaudeCodeAdapter(permission_mode="plan")`. Full suite in clean Docker (L006) + CI.
4. **What could break:** `initialize_project` defaults (`default_adapter="dummy"`,
   `adapter_options=None`) keep every existing caller byte-identical (dummy placeholder already
   carried `enabled: true`). `run_claude`/adapter default `permission_mode=None` → no flag →
   identical commands for existing flows. Binary check runs before any file is written, so a
   failed init leaves no partial scaffold.

## Review section

### Validation
- Host: 471 passed, ruff clean, compileall clean.
- Clean Docker (`python:3.12-slim`, latest deps): re-run after review fixes.
- Manual smoke (real claude 2.1.170): init verifies binary + writes config; bad adapter rejected;
  `create_adapter_from_config` on the generated config returns `ClaudeCodeAdapter(permission_mode="plan")`.

### Adversarial review (4 dimensions × per-finding verification): 11 confirmed / 21 raw, 10 refuted
**Fixed (8):**
- Scaffold left dummy `enabled: true` alongside the chosen adapter → exactly one default enabled now
  (`adapters["dummy"]["enabled"] = default_adapter == "dummy"`), asserted in the CLI test.
- `get_claude_version` timeout message now includes the duration; empty `--version` output now
  raises instead of "verifying" an empty string. Both paths tested.
- permission-mode validation was duplicated CLI↔adapter → extracted a single domain authority
  `runner.validate_permission_mode()`; adapter `__init__` and `forge init` both call it.
- Test gaps: all 6 modes parametrized; gold contract-set test (forces deliberate re-capture if
  claude changes choices, L007); factory rejects invalid mode.

**Rejected (3, with reasons):**
- "Missing init use case layer" — init→scaffold direct call is a documented pre-existing pattern;
  extracting `use_cases/init.py` is a refactor for its own PR (refactor ≠ feature commit), deferred.
- "adapter_options unvalidated at scaffold layer" — internal caller (CLI) validates at the
  boundary; re-validating internal paths is explicitly discouraged (defensive-at-boundaries-only).
- "kebab→snake untested" — factually wrong; the CLI test passes `--adapter claude-code` and
  asserts `default_adapter == "claude_code"`.

**Refuted by verifiers (10):** incl. partial-scaffold claim (binary check runs before any file
write), CLI-imports-adapters layer claim (adapters is not in the documented forbidden list).

---

# Phase 05.5 exit checklist — kill-criterion run + integration fixes

**SRS traceability:** FR-KA-001 (spawn produces real artifacts), FR-KA-003 (kernel-agnostic
executor seam) — the phase-doc kill criterion: a real `forge agent run` end-to-end
(persona → subprocess → artifact → contract pass).

### What the real run exposed (3 bugs DummyAdapter masked)

- [x] **E2E-1** — `extract_text_outputs` emitted `OutputArtifact(path="")`; the ArtifactRegistry
  correctly rejects empty paths, aborting the run AFTER the paid spawn. Fix: `extract_outputs(result,
  project_root)` derives file artifacts from Write/Edit/NotebookEdit tool uses (relativized,
  outside-project skipped, deduped); transcript text moved to `metadata["final_text"]`. Replay
  derives identically (`replay_session` gained `project_root`).
- [x] **E2E-2** — `_stage_context` omitted the contract's `required_outputs`, so a real kernel
  never learned its deliverables. Fix: context now carries path/type/description/blocking per
  requirement (sync + async executor paths). Regression test captures the context.
- [x] **E2E-3** — `claude -p` opened a conversation ("What are you building?", 0 tool uses, $0.024
  wasted) instead of producing artifacts. Fix: `_build_prompt` appends a claude-specific
  execution directive (non-interactive batch run; create `required_outputs` at exact paths;
  record assumptions instead of asking).

### Gate answers
1. **SRS:** FR-KA-001/FR-KA-003 + phase-doc kill criterion.
2. **Files:** `adapters/claude_code/adapter.py`, `adapters/claude_code/replay.py`,
   `agents/executor.py`; tests in 3 files.
3. **Verify:** 475 tests green (host + Docker); REAL e2e: `forge agent run --stage srs` with
   claude_code/haiku → SRS.md written by the agent (6 tool uses, 73s, $0.08), contract passed,
   outputs `['SRS.md']` registered, run record persisted.
4. **What could break:** outputs derivation changed for claude_code only (dummy untouched);
   replay stays output-identical to live spawn by construction; pre-fix recorded streams replay
   fine (outputs derived from the same stream events, just a different projection).

### Adversarial review (4 dimensions × per-finding verification): 7 confirmed / 12 raw, 5 refuted
**Fixed (5):**
- Out-of-project writes were skipped silently → `log.warning` now names the tool and path.
- Generic-vs-claude-specific directive boundary → executor now signals `execution_mode: "batch"`
  in the stage context (any adapter can honor it); the claude-phrased directive stays in the
  adapter, which is correct since `claude -p` is always batch.
- `final_text`-in-metadata rationale documented at the metadata seam.
- NotebookEdit added to the output-extraction test; executor→ClaudeCodeAdapter integration test
  asserts the real `-p` prompt names `SRS.md` + the batch directive.

**Rejected (2, with reasons):**
- "Replay of old runs breaks on missing `final_text`" — no production code bracket-accesses it;
  the only test that asserts it replays a new-format run; replay's contract (ADR-005) is the
  *current projection over recorded events* with metadata recorded verbatim — not byte-identical
  historical handles.
- "Fragile substring assertions" — the directive is prose; substring is the pragmatic check, and
  the structural check now exists via the `execution_mode` context assertion.

### Validation (final)
- Host: 476 passed, ruff clean, compileall clean. Docker re-run after review fixes.
- REAL kill-criterion e2e (pre-review-fix build): SRS.md written by the agent, contract passed,
  outputs registered. Integration test now pins the executor→adapter prompt contract.

---

# Open-source launch prep (decision D5) — LICENSE + README

**Traceability:** STATUS.md decision D5 (open-source kernel-first sequencing); owner approved
Apache-2.0 in session 2026-06-10.

- [x] **OSS-1** — `LICENSE`: canonical Apache-2.0 text (202 lines, fetched verbatim from
  apache.org). `pyproject.toml` license: Proprietary → Apache-2.0.
- [x] **OSS-2** — `README.md` rewritten for launch: what/why, kernel-adapter matrix (status per
  adapter, install extras), verified quickstart (`forge init --adapter claude-code`,
  `forge agent run --stage srs`), command surface generated from CLI introspection (not
  hand-listed), architecture diagram + layer rules, dev/contributing sections. Stale Phase-08.5
  content (133 tests, old roadmap) removed.

### Gate answers
1. **SRS/decision:** D5 launch milestone (owner-approved license choice).
2. **Files:** `LICENSE` (new), `README.md`, `pyproject.toml` (license field).
3. **Verify:** README links checked against the filesystem (caught + fixed a `docs/adr/` →
  `adr/` dead link); CLI flags in quickstart verified via `--help`; command table generated by
  introspecting the Typer app; 476 tests + ruff on host; Docker exercises the new packaging
  metadata via `pip install -e .[dev]`; CI gates the PR.
4. **What could break:** docs-only except the license metadata field — packaging validated in
  Docker/CI.
