# tasks/todo.md — Phase 05.5 Slice 2: ClaudeCodeAdapter Hooks + Event Store

> Task-ID note: the phase doc (`plan/PHASE-05.5-claude-code-adapter.md`) reserves
> P055.06–08 for Slice 2. The earlier multi-adapter expansion commit (`deb4bec`)
> loosely labelled itself "P055.06-12"; that label is informal. The phase-doc
> deliverables table is the single source of truth — P055.06–08 below are Slice 2.

## Slice 2 — Hook Capture + Event-Store Integration

**SRS traceability:**
- **FR-ES-001** (Immutable Event Store — all state changes recorded as append-only SQLite/WAL events) — record every stream-json line + spawn lifecycle to the Event Store.
- **FR-KA-002** (Capability Introspection — adapter reports *hook support* and *deterministic-output support*) — `supports("hook_events")` / `supports("replay")` are now backed by real recording.
- **FR-KA-005** (Event Translation — hooks remain kernel-agnostic) — `.claude/settings.json` hook lifecycle managed by the adapter, command injected by the caller.
- Honours ADR-005 (determinism boundary): the recorded stream is the foundation for Slice 3 replay (FR-ES-003).

### Tasks

- [x] **P055.06** — `adapters/claude_code/hooks.py`: `ClaudeSettingsHookWriter` context manager that merges PreToolUse/PostToolUse hook entries into `.claude/settings.json` on enter and restores the file (original bytes, or removes a file+dir it created) on exit. Hook command is caller-injected (no hardcoded `forge hook` — that CLI does not exist yet). Restore is resilient to FS failures.
- [x] **P055.07** — Extend `adapters/claude_code/runner.py` (`run_claude` gains an `on_event` callback) and `adapters/claude_code/adapter.py` (optional `event_store` + `hook_command` injection; records `AdapterSpawnStarted` → N×`AdapterStreamEvent` → `AdapterSpawnCompleted`/`AdapterSpawnFailed` under a per-spawn `run_id` stream; `run_id` exposed on `handle.metadata`; best-effort `_safe_append` recording).
- [x] **P055.08** — Tests: `tests/test_adapters_claude_code_hooks.py` (round-trip, restore, merge, malformed-JSON guard, restore resilience) + extended `tests/test_adapters_claude_code.py` (runner `on_event`, event-store recording happy/failed/empty/best-effort paths, distinct run_ids, hook lifecycle + install-failure terminal event). 404 tests total.

### Gate answers (required for multi-file change)

1. **Which SRS requirement?** FR-ES-001 (event store), FR-KA-002 (hook/determinism capability), FR-KA-005 (kernel-agnostic hooks). Replay foundation for FR-ES-003.
2. **Which files created/modified?**
   - New: `src/forge_os/adapters/claude_code/hooks.py`, `tests/test_adapters_claude_code_hooks.py`
   - Modified: `src/forge_os/adapters/claude_code/runner.py`, `src/forge_os/adapters/claude_code/adapter.py`, `tests/test_adapters_claude_code.py`
   - Docs: `plan/CURRENT_PHASE.md`, `plan/PHASE-05.5-claude-code-adapter.md`
3. **How verified?**
   - `tests/test_adapters_claude_code_hooks.py::TestRestore::test_restores_prior_settings` (round-trip)
   - `tests/test_adapters_claude_code.py::TestEventStoreRecording::test_records_started_stream_completed` (ordered event stream)
   - `tests/test_adapters_claude_code.py::TestEventStoreRecording::test_failed_run_records_failed_event`
   - `tests/test_adapters_claude_code.py::TestAdapterHookLifecycle::test_hooks_written_during_spawn_and_torn_down`
   - Full suite in clean Docker (`python:3.12-slim`, latest deps) per L006 — must be ≥371+new, ruff clean, compileall clean.
4. **What could break?**
   - Existing 12 `spawn_agent` tests (they `patch("subprocess.run")`) — preserved by keeping `subprocess.run` (batch) and making `on_event`/`event_store`/`hook_command` all optional (default None → identical prior behaviour).
   - `adapters → events` import: one-way (events/store.py is stdlib-only) — no cycle, no layer violation.
   - `.claude/settings.json` clobber: mitigated by capturing original bytes and restoring exactly; only removes a dir/file the writer itself created.

### Design decisions

- **Batch + `on_event`-during-parse** (not threaded streaming): the determinism *requirement* (record full stream-json transcript to the event store; replay reconstructs the handle without re-invoking) is fully met. True byte-by-byte streaming would add a stderr-drain thread + SQLite cross-thread hazard for negligible gain on a one-shot `claude -p` call (only partial-capture-on-crash differs, and a crash already records `AdapterSpawnFailed` with stderr). Documented tradeoff in the phase doc — not a hidden shortcut.
- **`hook_command` injected, default None**: avoids writing a `.claude/settings.json` that points at a not-yet-existing `forge hook` CLI. The mechanism (P055.06) lands and is tested; wiring to a live forge command follows when that command exists.
- **Event-type names** (`AdapterSpawnStarted` / `AdapterStreamEvent` / `AdapterSpawnCompleted` / `AdapterSpawnFailed`): PascalCase to match the EventStore convention (`StateSaved`), defined once as constants in `adapter.py`.

## Review section

### Validation
- Host: 404 passed, ruff clean, compileall clean.
- Clean Docker (`python:3.12-slim`, latest deps): 404 passed, ruff clean, compileall clean (re-run after review fixes).
- PLAYBOOK gates: G1 (no `forge_os.cli` in domain) clean; G3 (no `state.json`/`forge_dir` in adapters) clean; `adapters → events` is one-way (no cycle).

### Adversarial review (multi-agent, 4 dimensions × per-finding verification)
17 findings confirmed, 2 refuted. Applied judgment against the project's own rules (incl. No-Over-Engineering):

**Fixed (real defects):**
- Event-store recording was inconsistently fail-loud: a store write could abort a *successful* spawn or mask the real spawn error. Made recording uniformly **best-effort** via `_safe_append` (catches + logs with context, never raises), matching the `StateManager` dual-write precedent ("Event Store failure must not block state.json writes"). Resolves the started/stream/completed/failed asymmetry.
- Orphaned `AdapterSpawnStarted` on hook-install failure: `spawn_agent` now catches `Exception` (not just `ClaudeCodeSpawnError`), so a `ClaudeSettingsError` from hook install records a terminal `AdapterSpawnFailed` and re-raises the original error — no orphaned event, no masking.
- `ClaudeSettingsHookWriter.restore()` made resilient: filesystem failures during teardown (disk full, permissions, rmdir race) are caught + logged, never raised, so cleanup can't mask the wrapped block's outcome.
- Runner `on_event` docstring made honest (must not raise; the adapter's recorder absorbs its own infra failures).

**Rejected (YAGNI / test-implementation-not-behavior):**
- Re-entrance guard for `ClaudeSettingsHookWriter` — refuted: the class is single-use via context manager and the adapter builds a fresh instance per spawn. Added a single-use docstring note instead of a runtime guard for an impossible-in-practice state.
- Direct unit test of the private `_stream_recorder` boundary — behavior already covered by integration tests; testing structure over behavior.

**Tests added (9):** empty-stream records started+completed only; sequential spawns get distinct run_ids; no-store failure path still raises; event-store failure neither aborts a success nor masks a spawn error; hook-install failure records a terminal Failed event; restore failure logged-not-raised + doesn't mask block error; bounds-checked event ordering; failed-path stream payload content; empty parser input.

### Lesson candidate
Audit/observability side-channels (Event Store recording, hook config teardown) must be **best-effort relative to the primary operation** and must never mask its error — consistent with `StateManager`'s dual-write. Captured here rather than `tasks/lessons.md` (which is reserved for user corrections); promote to a lesson if this recurs.
