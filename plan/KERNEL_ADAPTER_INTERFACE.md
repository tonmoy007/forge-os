# Kernel Adapter Interface

## Problem

Without a clear abstraction, Forge OS becomes tied to one AI vendor or one agent runtime.

## Solution

Define a minimal, language-agnostic `KernelAdapter` interface. The Orchestration Engine speaks only to this interface. Provider-specific behavior belongs inside adapter implementations.

## Minimal Language-Agnostic Interface

The canonical interface capabilities are:

- `spawn_agent(persona: AgentDefinition, context: str, tools: ToolList) -> AgentHandle`
- `on_event(event: LifecycleEvent, session: SessionState) -> EventResponse`
- `get_default_tools() -> ToolList`

These three capabilities are the required portability boundary.

## Optional Runtime Control Capabilities

Implementations may also support these optional capabilities when the provider/runtime allows them:

- `stop_agent(handle: AgentHandle) -> StopResult`
- `get_status(handle: AgentHandle) -> AgentStatus`
- `stream_events(handle: AgentHandle) -> EventStream`
- `resume_agent(handle: AgentHandle, session: SessionState) -> AgentHandle`

Optional capabilities must be discoverable. Forge OS Core must not assume they exist unless the adapter declares support for them.

## Interface Responsibilities

### `spawn_agent`

Starts an agent using:

- Agent persona
- Pruned context
- Tool permissions
- Output contract metadata
- Stage/session metadata

Returns a normalized `AgentHandle` that Forge OS can track without knowing provider-specific IDs directly.

### `on_event`

Receives Forge lifecycle events and returns normalized responses.

Examples of events:

- `SessionStart`
- `UserPromptSubmit`
- `StageStarted`
- `PreToolUse`
- `PostToolUse`
- `Stop`
- `SubagentStop`
- `SessionEnd`

### `get_default_tools`

Returns the adapter's default abstract tool list. Forge OS Core then intersects this list with the active agent's security/tool profile.

The adapter must never grant tools beyond what Forge OS permits.

## Required Adapter Implementations

The architecture supports, at minimum:

- `ClaudeCodeAdapter` — maps Forge lifecycle and agent personas to Claude Code/plugin hook behavior.
- `CodexAdapter` / `OpenAIAdapter` — maps Forge lifecycle and agent personas to OpenAI/Codex-style completions and tool-calling behavior.
- `OpenClawAdapter` — maps Forge lifecycle and agent personas to the OpenClaw Gateway over HTTP/WebSocket.
- `OpenCodeAdapter` — maps Forge lifecycle and agent personas to OpenCode-style execution/runtime behavior.
- `LocalLLMAdapter` — wraps local inference runtimes such as llama.cpp or compatible local model servers.
- `HumanAdapter` — allows a user to manually perform an agent role for debugging, auditing, or no-AI operation.
- `DummyAdapter` — deterministic test adapter required for CI and early development.

## Selected Implementation Order

The selected implementation order is tracked in `plan/ADAPTER_ROADMAP.md`:

1. `DummyAdapter`
2. `ClaudeCodeAdapter`
3. `CodexAdapter`
4. `OpenClawAdapter`
5. `OpenCodeAdapter`
6. `LocalLLMAdapter`
7. `HumanAdapter`

## Core Rule

The Orchestration Engine must never call provider-specific APIs directly. It must speak only to `KernelAdapter`.

This makes Forge OS future-proof, testable, and independent from any one AI vendor or runtime.
