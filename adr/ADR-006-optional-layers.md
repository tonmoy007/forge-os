# ADR-006 — Optional Advanced Layers

Status: accepted

Date: Phase 00

## Context

Forge OS has ambitious capabilities including daemon operation, Dreamer maintenance, channels, OpenClaw, global skills, and plugins. These features should not make the core CLI hard to install, test, or use offline.

## Decision

Advanced capabilities are optional layers. The core CLI and deterministic project lifecycle must work without daemon, channel adapters, OpenClaw, plugins, or real AI providers.

## Consequences

Positive:

- Phase 01–04 can produce useful local value quickly.
- Core remains small and testable.
- Optional integrations can mature independently.
- Users can choose their trust and dependency surface.

Tradeoffs:

- Some integration convenience is deferred.
- Extension points must be designed without prematurely implementing full systems.

## Implementation Guidance

- Build interfaces/placeholders only when required by the current phase.
- Do not implement future-phase behavior early.
- Optional layer failures must not advance or corrupt state.
- Optional dependencies belong in extras or plugin packages.
