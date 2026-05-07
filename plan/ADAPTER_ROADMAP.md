# Kernel Adapter Roadmap

## Decision

Adapters will be implemented in this order:

1. `DummyAdapter`
2. `ClaudeCodeAdapter`
3. `CodexAdapter`
4. `OpenClawAdapter`
5. `OpenCodeAdapter`
6. `LocalLLMAdapter`
7. `HumanAdapter`

## Adapter Principles

- Forge OS Core owns orchestration, gate decisions, state, memory, ADG, and audit logs.
- Adapters only execute agents or translate lifecycle events.
- Adapters must be loaded through configuration or plugin registration.
- Core must never import provider-specific SDKs directly.
- Adapter failure must not corrupt Forge state.
- Adapter results must be normalized before entering Forge Core.

## Required Adapter Interface

The canonical minimal language-agnostic interface is defined in `plan/KERNEL_ADAPTER_INTERFACE.md`.

Required capabilities:

- `spawn_agent(persona: AgentDefinition, context: str, tools: ToolList) -> AgentHandle`
- `on_event(event: LifecycleEvent, session: SessionState) -> EventResponse`
- `get_default_tools() -> ToolList`

Optional runtime control capabilities:

- `stop_agent(handle)`
- `get_status(handle)`
- `stream_events(handle)`
- `resume_agent(handle, session)`

The Orchestration Engine must speak only to this adapter interface.

## Adapter Implementation Notes

### 1. DummyAdapter

Purpose:

- Deterministic testing
- No external dependency
- Enables CI and early end-to-end stage flow

Phase:

- Phase 05

### 2. ClaudeCodeAdapter

Purpose:

- First real AI execution adapter
- Maps Forge agent personas and tool profiles to Claude Code behavior

Phase:

- After Phase 05 is stable, before or during the first real AI execution release.

### 3. CodexAdapter

Purpose:

- Second real AI execution adapter
- Represents the OpenAI/Codex-style adapter family for completions/tool-calling workflows
- Must use the same normalized adapter contract as ClaudeCodeAdapter

Phase:

- After ClaudeCodeAdapter.

### 4. OpenClawAdapter

Purpose:

- Optional execution substrate for hosted agents, channels, skills, and runtime behavior
- Bridges Forge lifecycle events to OpenClaw Gateway HTTP/WebSocket APIs

Phase:

- Interface can be planned early.
- Full implementation belongs to Phase 11 unless explicitly pulled forward.

### 5. OpenCodeAdapter

Purpose:

- Adapter for OpenCode-style execution/runtime flows.

Phase:

- After OpenClawAdapter unless priority changes.

### 6. LocalLLMAdapter

Purpose:

- Local model execution.
- Useful for privacy/offline workflows.

Phase:

- After hosted/runtime adapters.

### 7. HumanAdapter

Purpose:

- Manual/offline fallback where a human performs the agent role.
- Useful for debugging, regulated environments, or no-AI operation.

Phase:

- Last in current priority order.
- May be stubbed earlier if needed for interface tests, but full implementation should wait.
