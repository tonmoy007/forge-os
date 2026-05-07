# Forge OS Questions Tracker

Use this file for decisions that cannot be safely guessed during implementation.

## Open Questions

None currently.

## Resolved Questions

### Q1 — Runtime

Decision: Python 3.11+.

Implementation guidance:

- Use Python 3.11+ as the default runtime.
- Prefer `typer` for CLI, `pydantic` for schemas, `rich` for output, and `pytest` for tests.

### Q2 — Kernel Adapter Priority

Decision: Implement adapters in this priority order:

1. `DummyAdapter`
2. `ClaudeCodeAdapter`
3. `CodexAdapter`
4. `OpenClawAdapter`
5. `OpenCodeAdapter`
6. `LocalLLMAdapter`
7. `HumanAdapter`

Implementation guidance:

- `DummyAdapter` is required first so the orchestration engine can be tested deterministically.
- `HumanAdapter` remains useful for offline/manual fallback, but it is no longer the second implementation priority.
- Provider-specific adapters must stay outside Forge OS core and communicate only through the Kernel Adapter Interface.

### Q3 — OpenClaw Adapter Architecture

Decision: OpenClaw integration should follow the adapter architecture below:

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

Implementation guidance:

- Forge OS Core remains the source of truth.
- OpenClaw is an optional execution substrate.
- OpenClaw memory is optional and must not overwrite Forge OS state, gates, ADG, LKG, or artifacts.
- Gate requests are forwarded back to Forge OS Core, not decided by OpenClaw.

### Q4 — Initial Distribution Target

Decision: Use the recommended distribution path.

Implementation guidance:

1. Start as a local Python package.
2. Support `pipx` installation when packaging is ready.
3. Consider standalone binaries later.
