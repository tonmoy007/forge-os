# tasks/todo.md — Phase 05.5 Slice 4: Adapter selection + `forge adapter status`

> Slices 1–3 + 1.5 (real-contract fix) merged. CI live (PRs gated). This is Slice 4
> per the phase-doc deliverables table (P055.11-12).

## Slice 4 — make ClaudeCodeAdapter selectable + `forge adapter status` (P055.11-12)

**SRS traceability:**
- **FR-KA-003** (Multiple Implementations — user switches kernels by config change; no core code change) — selecting `claude_code` via `config.default_adapter` must actually work.
- **FR-KA-002** (Capability Introspection — adapter reports hook support, deterministic-output) — `forge adapter status` surfaces availability + capabilities.

### Root problem found (P055.11)
`_claude_code_factory` (`adapters/registry.py:97`) is **broken**: it passes `model=…` to
`ClaudeCodeAdapter(...)`, which has no `model` param (would `TypeError` on selection), and — unlike
`_codex_factory` — it has **no `shutil.which("claude")` binary check**. So `default_adapter: claude_code`
crashes instead of producing a clean error or a working adapter.

### Tasks

- [x] **P055.11a** — Fix `_claude_code_factory`: `shutil.which(claude_bin)` check → clean `AdapterRegistryError` with an install hint if absent (mirrors `_codex_factory`); pass `claude_bin` + optional `model` correctly.
- [x] **P055.11b** — Thread real model support: `ClaudeCodeAdapter(model=None)` → `run_claude(model=...)` → `--model <model>` only when configured (so `config.adapters.claude_code.model` is honoured instead of silently ignored).
- [x] **P055.12** — `forge adapter status`: a new `use_cases/adapters.py::AdapterUseCases.status()` that reports, per adapter, {enabled, default, available, reason, capabilities} — *available* = the factory constructs without raising and isn't a placeholder. New `@adapter_app.command("status")` renders it.

### Selection-policy decision (deviation from stale phase-doc text, documented)
The phase doc's Slice 4 prose says "auto-pick claude_code when available, else fall back to DummyAdapter."
The **real** seam is `create_adapter_from_config` (config-driven `default_adapter`), not the
`use_cases/gates.py` the doc names. We keep config-driven selection and **fail loud** when the configured
adapter is unavailable — silent fallback to Dummy would produce fake artifacts while the user believes
they're running a real kernel, violating the project's "fail loud / no silent failures" rule. Out-of-the-box
default is already `dummy`, so a fresh clone works without claude; you only get claude_code by explicitly
configuring it, and then a missing binary is a clear error (+ visible in `adapter status`).

### Gate answers
1. **SRS:** FR-KA-003 (config-driven kernel switch), FR-KA-002 (capability/availability introspection).
2. **Files:** modify `adapters/registry.py`, `adapters/claude_code/adapter.py`, `adapters/claude_code/runner.py`, `cli/main.py`; new `use_cases/adapters.py`, `tests/test_use_cases_adapters.py`; extend `tests/test_adapters_claude_code.py` (factory + --model) and the CLI test for `adapter status`.
3. **Verify:** factory raises when `shutil.which` is None / constructs when present; `--model` flag threaded; `status()` marks claude_code available iff binary present (mock `shutil.which`); `forge adapter status` renders + exits 0. Full suite in clean Docker (L006) + GitHub CI.
4. **What could break:** `create_adapter_from_config` for `default_adapter: dummy` (the default) is unchanged → existing flows unaffected. The factory fix only changes the claude_code path (currently crashing). `--model` defaults None → no `--model` arg → identical to current behaviour for existing tests.

## Review section

### Validation
- Host: 440 passed, ruff clean, compileall clean.
- Clean Docker (`python:3.12-slim`, latest deps): re-run after review fixes (pending confirm at write time).
- GitHub CI: green on the PR (now live).
- Manual smoke: `forge adapter status` shows `claude_code` available with the binary on PATH, bridged adapters (`claude_raw`, `human`) now show real capabilities, `codex` shows its install hint, `openclaw` "not implemented".

### Adversarial review (4 dimensions × per-finding verification): 7 confirmed / 8 raw → 3 distinct issues
- **Bridged adapters showed empty capabilities** (the `type: ignore`-flagged finding was reported 4× — counted once). `getattr(adapter, "optional_capabilities", …)` returned empty for `AsyncToSyncBridge`-wrapped adapters. Fixed by adding an `optional_capabilities` property on the bridge that derives capability names from the inner adapter's `KernelCapabilities` flags (streaming/vision/hooks_native/…). Left `supports()` untouched (separate API, out of scope).
- **`registry: object` + `type: ignore`** in `_probe` → typed it `AdapterRegistry`, dropped the suppression.
- **Env-dependent status tests** (L001) → the two tests probed all adapters (incl. `claude_code`) without mocking `shutil.which`, so they passed on host *and* Docker only by luck. Mocked `shutil.which` in both for determinism.
- Refuted (correctly): a false "unused import" claim (`load_config` is used).
- Tests added: bridge `optional_capabilities` derivation; the two status tests made deterministic.
