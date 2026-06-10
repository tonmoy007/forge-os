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
