# Forge OS Test Strategy

Status: Phase 00 foundation decision.

This document defines the testing approach for Forge OS. It is intended to guide Phase 01+ implementation.

## Testing Goals

Forge OS must be safe to evolve because it manages project lifecycle state. Tests must verify determinism, state integrity, gate behavior, adapter boundaries, and safe degradation.

Primary goals:

1. Deterministic state transitions.
2. Atomic and auditable state writes.
3. Open-format compatibility.
4. Adapter isolation from core orchestration.
5. Gate and hook timeout behavior.
6. Clear failure modes and recoverability.
7. No dependency on real AI providers for core tests.

## Test Layers

| Layer | Purpose | Required Starting Phase |
|---|---|---|
| Unit tests | Validate schemas, pure functions, state transitions, policies | Phase 01 |
| Contract tests | Validate adapter interface behavior using `DummyAdapter` | Phase 05 |
| Integration tests | Validate CLI plus filesystem behavior in temporary projects | Phase 01 |
| Golden file tests | Validate deterministic generated files such as state mirrors and reports | Phase 02 |
| Failure-mode tests | Validate corrupted config, missing files, timeout, hook/adapters failures | Phase 03 |
| Security tests | Validate tool permission policy, approvals, and audit log entries | Phase 08 |
| Compatibility tests | Validate schema version migration and unknown-field preservation | Phase 02+ |

## Required Test Principles

- Tests must not require network access unless explicitly marked as external/integration-provider tests.
- Tests must not require real AI provider credentials.
- Core tests must use `DummyAdapter` or test doubles.
- Filesystem tests must use temporary directories.
- Tests must avoid relying on wall-clock timing except through injectable clocks or bounded tolerances.
- External command tests must use explicit timeouts.
- Destructive operations must be tested with approval-denied and approval-granted paths.
- Generated open-format files must be deterministic enough for stable assertions.

## Initial Phase 01 Test Scope

Phase 01 should add tests for:

1. Package import.
2. CLI help execution.
3. `forge init` creates the expected `.forge/`, `pipeline/`, and `tasks/` layout.
4. `forge init` refuses unsafe overwrite unless explicitly allowed.
5. `forge status` handles initialized and uninitialized directories.
6. Config defaults validate against schema models.
7. CLI commands produce non-zero exits for invalid inputs.

## Phase 02 Test Scope

Phase 02 should add tests for:

1. Minimal and standard profile stage ordering.
2. Valid and invalid stage transitions.
3. Atomic state write behavior.
4. Append-only event log behavior where introduced.
5. Human-readable state mirror generation.
6. Corrupt state detection and safe failure.

## Phase 03 Test Scope

Phase 03 should add tests for:

1. Lifecycle event emission.
2. Hook registration and execution order.
3. Non-blocking hook failure behavior.
4. Blocking hook failure behavior when explicitly configured.
5. Hook timeout enforcement.

## Phase 04 Test Scope

Phase 04 should add tests for:

1. Required file gates.
2. Pattern gates.
3. Gate result statuses: pass, fail, warn, skipped, error.
4. Timeout behavior for executable checks.
5. Gate report determinism.

## Phase 05 Test Scope

Phase 05 should add tests for:

1. `KernelAdapter` protocol conformance.
2. `DummyAdapter` deterministic output.
3. Adapter capability discovery.
4. Adapter failure normalization.
5. Tool list intersection with security profile.
6. Core does not import provider-specific SDKs.

## Test Tooling

Recommended tools:

- `pytest` for test execution.
- `pytest-cov` for coverage when useful.
- `ruff` for linting and formatting.
- `mypy` or `pyright` for static type checking once models stabilize.
- `hypothesis` may be introduced later for schema/property tests.

## Minimum Check Command Set

Once the Python scaffold exists, the default local checks should become:

| Check | Purpose |
|---|---|
| `pytest` | Run test suite |
| `ruff check` | Linting |
| `ruff format --check` | Formatting |
| Type checker command | Static typing once configured |

## Coverage Expectations

Coverage should be meaningful, not vanity-driven.

Required high-coverage areas:

- State transitions.
- Schema validation.
- Gate status calculation.
- Security policy decisions.
- Adapter normalization.
- State persistence and recovery.

Lower coverage is acceptable for:

- CLI display formatting.
- Optional provider-specific adapters before they are stable.
- Experimental plugin integrations.

## Provider Adapter Testing

Provider adapters must have two categories of tests:

1. Offline contract tests using mocked transport or fake clients.
2. Optional live tests gated behind explicit environment variables and credentials.

Live provider tests must never run in the default test suite.

## Test Data Policy

- Test fixtures must not contain secrets.
- Test project directories should use tiny representative files.
- Golden files must be reviewed when schema versions change.
- Fixture names should describe lifecycle stages and failure modes clearly.

## CI Readiness Bar

Before release 0.1, CI should run:

1. Unit tests.
2. CLI integration tests.
3. Linting.
4. Format check.

Before release 1.0, CI should additionally run:

1. Type checks.
2. Security policy tests.
3. Schema compatibility tests.
4. Adapter contract tests.
