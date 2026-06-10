# tasks/todo.md — Phase 05.5 Slice 5: SecurityEnforcer pre-spawn gate

> Slices 1–4 + 1.5 (real-contract fix) merged. CI live (PRs gated). This is Slice 5
> per the phase-doc deliverables table (P055.13-14).

## Slice 5 — SecurityEnforcer check before the subprocess spawns (P055.13-14)

**SRS traceability:**
- Security baseline / **FR-NEG** (policy & governance): every privileged action validated against
  the project security profile with an audit trail (`.forge/security-audit.jsonl`); least
  privilege + fail-closed on DENY (BUILD_SPEC security rules, ADR least-privilege).

### Tasks

- [x] **P055.13** — Inject `security_enforcer: SecurityEnforcer | None = None` into
  `ClaudeCodeAdapter` (DI, same pattern as `event_store`/`hook_command`). In `spawn_agent`,
  before the hook context / `run_claude`, call
  `validate_action(actor, "execute_command", target=claude_bin, capability="shell")` —
  the same action/capability pair as `SecurityEnforcer.run_command`, so one capability rule
  governs both paths. On `DENIED`: raise `ClaudeCodeSpawnError`; the existing
  `except` boundary records the terminal `AdapterSpawnFailed` event (best-effort, Slice 2
  pattern). Enforcer audits every decision itself. `WARNED` (prompt policy) does not block —
  matches `run_command` semantics. Default `None` = no gate (existing tests stay green).
- [x] **P055.14** — Tests (`tests/test_adapters_claude_code.py::TestSecuritySpawnGate`):
  deny blocks spawn with `subprocess.run` NOT called; deny records Started→Failed (no
  Completed) in the event store; allow proceeds and validates action/capability args;
  WARNED does not block; real `SecurityEnforcer` + default-DENY profile writes the audit
  entry to `.forge/security-audit.jsonl`; no enforcer = no gate.

### Gate answers
1. **SRS:** security baseline / FR-NEG (policy & governance, audit trail, least privilege).
2. **Files:** modify `adapters/claude_code/adapter.py`; extend `tests/test_adapters_claude_code.py`.
3. **Verify:** 6 new tests above; full suite (446) + ruff + compileall on host, clean
   `python:3.12-slim` Docker (L006), GitHub CI on the PR.
4. **What could break:** default `security_enforcer=None` keeps every existing call site and
   test unchanged; the gate runs inside the existing failure boundary, so event-stream
   invariants (terminal event after Started) hold. The gate fires before `_hook_context()`,
   so a denied spawn never touches `.claude/settings.json`.

## Review section

### Validation
- Host: 447 passed, ruff clean, compileall clean.
- Clean Docker (`python:3.12-slim`, latest deps): 447 passed + ruff clean (re-run after review fixes).
- GitHub CI: gates the PR.

### Adversarial review (4 dimensions × per-finding verification): 7 confirmed / 10 raw, 3 refuted
- **Enforcer-exception semantics (high) + audit-failure robustness (medium)** — the gate is
  **fail-closed by design**: an enforcer exception (audit log unwritable, enforcer bug) aborts the
  spawn before the subprocess, surfaces the *original* error (distinguishable from a denial, which
  is always `ClaudeCodeSpawnError` "security profile denied"), and still records the terminal
  Failed event. We deliberately did NOT make `SecurityEnforcer.validate_action` swallow audit
  errors — a silently lossy security audit trail violates fail-loud and is out of slice scope.
  Documented the contract in both docstrings + added `test_enforcer_exception_fails_closed`.
- **Audit fragmentation (medium)** — intentional split of concerns, now documented in the class
  docstring: `.forge/security-audit.jsonl` is authoritative for security decisions; the event
  store records only spawn lifecycle.
- **Test gaps (high/medium/medium/low)** — all fixed: fail-closed test added; full actor-dict
  positional-arg assertion; audit-entry assertions deepened (actor, target, audit_id,
  schema_version, timestamp); `match="security profile denied"` on the second deny test.
- Refuted (correctly): cross-test event-store pollution (tmp_path isolation), FAILED-decision
  gap (`validate_action` never returns FAILED — unreachable), `.forge` dir pollution (tmp_path).
