# ADR-002 — Local-First Core

Status: accepted

Date: Phase 00

## Context

Forge OS should support project lifecycle orchestration even without network access or AI provider credentials. It must remain usable in private, regulated, offline, and deterministic test environments.

## Decision

Forge OS core is local-first. Core CLI functionality must not require network access, AI provider credentials, OpenClaw, channels, daemon services, or plugins.

Offline operation must remain possible through deterministic core behavior and offline-compatible adapters such as `DummyAdapter` and eventually `HumanAdapter`.

## Consequences

Positive:

- Core workflows are testable without external services.
- Users can run Forge OS in private or regulated environments.
- Provider outages do not make the local project state unusable.
- The system remains auditable and deterministic.

Tradeoffs:

- Some advanced automation requires optional configuration.
- Provider/channel convenience must be implemented as optional layers rather than shortcuts inside core.

## Implementation Guidance

- Do not add network calls to core initialization/status workflows.
- Treat provider adapters and OpenClaw as optional execution surfaces.
- Keep project state on disk in open formats.
