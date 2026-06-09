# tasks/todo.md — Phase 05.5 Slice 3: ClaudeCodeAdapter Replay

> Slice 2 (P055.06-08, hooks + event-store recording) is merged (PR #3). This is
> Slice 3 per the phase-doc deliverables table.

## Slice 3 — Replay from the Event Store (P055.09-10)

**SRS traceability:**
- **FR-ES-003** (Replay — reconstruct state by re-projecting events; replay does NOT re-invoke AI agents).
- **FR-ES-004** (Projection Engine — current state derived by replaying events).
- Honours ADR-005 (determinism boundary): the same `run_id` yields the same `AgentHandle` every time, without the subprocess.

### Tasks

- [x] **P055.09** — `adapters/claude_code/replay.py`: `replay_session(event_store, run_id) -> AgentHandle` re-projects the recorded `AdapterSpawnStarted` / `AdapterStreamEvent` / `AdapterSpawnCompleted` stream into the original `AgentHandle` **without** invoking the subprocess. Single error boundary → `ReplayError` for missing / incomplete / failed / malformed runs. `ClaudeCodeAdapter.replay_session(run_id)` delegates to it (lazy import → no import cycle).
- [x] **P055.10** — Tests: `tests/test_adapters_claude_code_replay.py` (18 tests) — replay reconstructs the exact original handle; `subprocess.run` never called (happy + failed paths); deterministic; projects from hand-crafted store events; ReplayError on unknown/incomplete/failed/no-store/malformed-record.

### Supporting changes to Slice 2 recording (needed for faithful replay)
- `adapter.py`: extract `extract_text_outputs(result)` as a module function (shared by live spawn and replay — DRY, single projection of text → outputs).
- `adapter.py`: record `handle_id` in the `AdapterSpawnCompleted` event (the only non-derivable handle field; everything else is reconstructed from the stream + Started/Completed records).

### Gate answers (multi-file change)

1. **Which SRS requirement?** FR-ES-003 (replay), FR-ES-004 (projection engine); ADR-005 determinism.
2. **Which files?**
   - New: `src/forge_os/adapters/claude_code/replay.py`, `tests/test_adapters_claude_code_replay.py`
   - Modified: `src/forge_os/adapters/claude_code/adapter.py` (extract helper + record handle_id + `replay_session` method), `src/forge_os/adapters/claude_code/__init__.py` (export `ReplayError`)
   - Docs: `plan/CURRENT_PHASE.md`, `plan/PHASE-05.5-claude-code-adapter.md`
3. **How verified?**
   - `test_replay_reconstructs_handle_without_subprocess` (`subprocess.run` asserted not called during replay)
   - `test_replay_equals_original_handle` (full `AgentHandle` equality after a recorded spawn)
   - `test_replay_is_deterministic` (two replays of one run_id are equal)
   - `test_replay_failed_run_raises`, `test_replay_unknown_run_raises`, `test_replay_incomplete_run_raises`, `test_replay_no_event_store_raises`
   - Full suite in clean `python:3.12-slim` Docker (latest deps, per L006).
4. **What could break?**
   - Recording `handle_id` is additive to the Completed payload — existing recording tests unaffected.
   - Extracting `extract_text_outputs` is a behavior-preserving refactor of a 3-line method (call site updated in the same change); existing spawn tests unaffected.
   - Import cycle (adapter ↔ replay) avoided: replay imports from adapter at module level; adapter imports replay **lazily** inside `replay_session`.

### Design decisions
- **Projection, not snapshot**: replay rebuilds a `RunResult` from the recorded `AdapterStreamEvent`s and re-derives `outputs` via the shared `extract_text_outputs` — proving the recorded stream is sufficient (the determinism showcase), not just reading back a stored answer. `metadata` is read verbatim from the recorded Completed event (it *is* the recorded projection; re-deriving would duplicate `_build_metadata`). `handle_id` is restored from the record (non-derivable).
- **Failed runs raise**: the original `spawn_agent` returned no handle for a failed run (it raised); replay mirrors that — `ReplayError` carrying the recorded returncode + error, deterministic every time.

## Review section

### Validation
- Host: 422 passed, ruff clean, compileall clean.
- Clean Docker (`python:3.12-slim`, latest deps): 422 passed, ruff clean, compileall clean (re-run after review fixes).
- No import cycle (verified by direct `import forge_os.adapters.claude_code.replay`); G1/G3 clean.

### Adversarial review (4 dimensions × per-finding verification): 9 confirmed / 15 raw
Applied judgment against the project's own rules — including the **trust-internal-data** rule (don't re-validate data validated at write) vs. **error-handling.md** (wrap DB/file reads). The review even contradicted itself (confirmed missing-`handle_id` → KeyError but refuted the identical concern for `status`/`metadata`).

**Fixed — one error boundary instead of scattered guards:** wrapped the event-store read/projection in a single `try/except (KeyError, TypeError, JSONDecodeError) → ReplayError(...)`. This converts deserialization failures (missing keys from an older schema, corrupt JSON) into a clean domain error uniformly — covering handle_id (F1), type/raw (F2), and the refuted status/metadata/persona_id cases — without per-field `.get()` noise. Control-flow `ReplayError`s (no-start/incomplete/failed) pass through untouched (not in the catch tuple). Justified by error-handling.md ("wrap DB reads") for a user-facing op (`forge replay`); not over-engineering — it's a single boundary at the read seam.

**Rejected (with reasoning):**
- F5 (non-dict `raw` → AttributeError): pure-corruption scenario; deliberately did NOT catch `AttributeError` (too broad — would mask real bugs). Consistent with `EventStore.replay_state`'s unguarded reads and the trust-internal-data rule.
- The refuted strict-access findings (status/returncode/metadata/persona_id/adapter, multi-run isolation, persona-None): the single boundary already covers the missing-key cases uniformly; no per-field defensive code added.

**Tests added (6):** completed event missing `handle_id` → ReplayError; stream event missing keys → ReplayError; failed-only/no-start → "no start event"; failed-run replay invokes no subprocess; replay projects outputs from hand-crafted store events (proves store-sourced, fixture replay per P055.10); determinism asserts `handle_id` equality explicitly.
