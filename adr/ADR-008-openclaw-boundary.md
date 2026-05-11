# ADR-008 — OpenClaw Integration Boundary

Status: accepted

Date: Phase 00

## Context

OpenClaw may provide useful agent runtime, channel, gateway, skill, and memory capabilities. Forge OS must be able to integrate with it without making it a core dependency or allowing it to own Forge state.

## Decision

OpenClaw integrates only through `OpenClawAdapter`, which implements the `KernelAdapter` interface and communicates with OpenClaw HTTP/WebSocket APIs or Gateway.

Forge OS core remains the source of truth for orchestration, gates, state, memory, ADG, backtrack decisions, and audit logs.

OpenClaw memory is optional runtime memory and must not overwrite Forge OS memory or state.

## Consequences

Positive:

- OpenClaw can be used as an optional execution substrate.
- Core remains usable without OpenClaw.
- Gate decisions remain deterministic and auditable.
- Integration can be deferred until API details are available.

Tradeoffs:

- Some OpenClaw-native capabilities must be translated into Forge events/proposals.
- Full integration may require mocks/placeholders until external API docs are stable.

## Implementation Guidance

- OpenClawAdapter forwards gate requests back to Forge OS core.
- If OpenClaw is unavailable, normalize the failure and preserve state.
- Do not add OpenClaw as a required dependency.
- Full OpenClaw integration belongs to Phase 11 unless intentionally pulled forward and recorded in a new ADR.
