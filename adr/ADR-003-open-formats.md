# ADR-003 — Open Project Formats

Status: accepted

Date: Phase 00

## Context

Forge OS persists project lifecycle state, gate definitions, event logs, lessons, and artifact graphs. Users must be able to inspect, back up, diff, and recover this data without a proprietary service.

## Decision

Persist Forge OS project data in open formats:

- YAML for human-editable configuration and definitions.
- JSON for canonical machine state.
- JSON Lines for append-only logs.
- Markdown for human-readable mirrors and decisions.
- GraphML for artifact dependency graphs.

## Consequences

Positive:

- Users can inspect and version project state.
- Data remains portable and recoverable.
- Tests can assert deterministic outputs.
- The system avoids vendor lock-in.

Tradeoffs:

- Care is required to keep human-readable mirrors from becoming divergent sources of truth.
- Schema migration must be planned once versions evolve.

## Implementation Guidance

- Every persisted schema includes `schema_version`.
- Machine-readable state is canonical where available.
- Human-readable mirrors should be generated.
- Unknown future-compatible fields should be preserved where safe.
