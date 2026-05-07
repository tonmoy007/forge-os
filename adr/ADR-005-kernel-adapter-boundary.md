# ADR-005 — Kernel Adapter Boundary

Status: accepted

Date: Phase 00

## Context

Forge OS needs to coordinate agent work without becoming tied to a single AI provider, CLI runtime, local model server, OpenClaw, or manual workflow.

## Decision

Forge OS core communicates with execution runtimes only through the language-agnostic `KernelAdapter` boundary.

Required capabilities:

- `spawn_agent(persona, context, tools)`.
- `on_event(event, session)`.
- `get_default_tools()`.

Optional capabilities must be discoverable:

- `stop_agent(handle)`.
- `get_status(handle)`.
- `stream_events(handle)`.
- `resume_agent(handle, session)`.

Concrete adapter implementation order:

1. `DummyAdapter`.
2. `ClaudeCodeAdapter`.
3. `CodexAdapter`.
4. `OpenClawAdapter`.
5. `OpenCodeAdapter`.
6. `LocalLLMAdapter`.
7. `HumanAdapter`.

## Consequences

Positive:

- Core remains provider-agnostic.
- Core tests can use deterministic adapters.
- Provider integrations can be optional dependencies.
- New runtimes can be added without rewriting orchestration.

Tradeoffs:

- Adapter normalization requires careful schema design.
- Some provider-specific capabilities may be unavailable through the minimal boundary.

## Implementation Guidance

- Core must not import provider-specific SDKs.
- Provider ids belong in adapter metadata, not as primary Forge ids.
- Adapter default tools must be intersected with Forge OS security policy.
- Adapter failures must normalize into auditable responses.
