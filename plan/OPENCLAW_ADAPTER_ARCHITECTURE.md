# OpenClawAdapter Architecture

## Decision

OpenClaw is integrated through a Kernel Adapter implementation. It is not part of Forge OS Core and must never become a required dependency.

## Architecture

┌──────────────────────────┐
│   Forge OS Core           │
│  Orchestration Engine     │
│  Gate Coordinator         │
│  Memory & Learning        │
└─────────┬────────────────┘
          │
          │  Kernel Adapter Interface
          │  (spawn_agent, send_event, …)
          │
┌─────────▼────────────────┐
│  OpenClawAdapter          │
│  - Translates Forge =>    │
│    OpenClaw agent configs │
│  - Maps hooks to          │
│    OpenClaw webhooks/API  │
│  - Listens for agent      │
│    output & termination   │
│  - Forwards gate requests │
│    back to Forge Core     │
└─────────┬────────────────┘
          │
          │  OpenClaw HTTP / WebSocket API
          │
┌─────────▼────────────────┐
│   OpenClaw Gateway        │
│   Agent Runtime           │
│   Channel & Skill System  │
│   Memory (optional)       │
└──────────────────────────┘

## Responsibilities

### Forge OS Core

Forge OS Core owns:

- Pipeline state
- Stage transitions
- Gate definitions and gate decisions
- Memory and learning source of truth
- ADG and context pruning decisions
- Backtrack/rework decisions
- Audit logs
- Security policy baseline

### OpenClawAdapter

OpenClawAdapter owns translation only:

- Convert Forge agent personas into OpenClaw agent configuration.
- Convert Forge tool profiles into OpenClaw tool/sandbox policies.
- Send lifecycle events to OpenClaw when needed.
- Listen for OpenClaw agent output and termination.
- Convert OpenClaw webhooks/API responses back into Forge events.
- Forward gate requests back to Forge Core instead of making gate decisions internally.

### OpenClaw Gateway

OpenClaw Gateway provides optional execution/runtime capabilities:

- Agent runtime
- Channel system
- Skill system
- Optional memory
- HTTP/WebSocket integration surface

## Memory Rule

OpenClaw memory is optional runtime memory. It must not overwrite:

- `.forge/state.json`
- `pipeline/state.md`
- `pipeline/gates.yaml`
- `pipeline/stages.yaml`
- `pipeline/dependencies.graphml`
- `.forge/lessons.yaml`
- Forge audit logs

Useful insights from OpenClaw can be proposed back to Forge OS as events, reflections, or lesson candidates, but Forge OS decides whether to persist them.

## Gate Rule

Gate requests must be forwarded back to Forge Core. OpenClaw may execute an agent or tool, but Forge OS Gate Coordinator decides pass/fail/warn/advisory.

## Failure Rule

If OpenClaw is unavailable:

1. OpenClawAdapter reports a normalized adapter failure.
2. Forge OS records the failure in the event log.
3. Forge OS keeps state consistent.
4. Forge OS may fall back to the next configured adapter.
5. No pipeline state is advanced solely because OpenClaw failed or disconnected.
