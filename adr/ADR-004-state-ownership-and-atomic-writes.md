# ADR-004 — State Ownership and Atomic Writes

Status: accepted

Date: Phase 00

## Context

Forge OS coordinates lifecycle state across stages, gates, hooks, agents, memory, and optional integrations. If many components can mutate state directly, the system becomes non-deterministic and hard to recover.

## Decision

Forge OS core is the sole owner and writer of canonical state. Agents, adapters, hooks, plugins, channels, and OpenClaw must not write `.forge/state.json` directly.

Canonical state writes must be atomic and validated before replacement.

## Consequences

Positive:

- State transitions remain deterministic.
- Failures from adapters/hooks cannot corrupt state directly.
- Recovery behavior can be reasoned about and tested.
- Auditing is simpler.

Tradeoffs:

- Execution surfaces must return proposals or normalized results instead of mutating state directly.
- Implementation requires clear service boundaries.

## Implementation Guidance

- Write to temporary files and replace atomically.
- Validate state before writing.
- Append lifecycle/security events for meaningful state changes.
- Treat corrupt state as a recovery condition, not as an invitation to overwrite user data.
