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

## ACP as Foundational Integration Layer

ACP (Agent Client Protocol) is an **open standard** (Apache 2.0) that standardizes communication between code editors and coding agents via JSON-RPC over stdio. ACP is **not** a new adapter type — it is a **transport and discovery layer** that all adapters can leverage.

```
┌──────────────────────────────────────────────────────────────┐
│                     Forge OS Adapter Layer                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ACP Registry (cdn.agentclientprotocol.com)                │
│        │                                                     │
│        ▼                                                     │
│   ACPRegistryAdapter ──► Agent manifest discovery           │
│        │                                                     │
│        ▼                                                     │
│   ACPClient (JSON-RPC / stdio)                              │
│        │                                                     │
│        ├──► Gemini CLI (ACP-native)                         │
│        ├──► GitHub Copilot CLI (ACP-native)                 │
│        ├──► Claude Code (via ACPx bridge)                   │
│        ├──► Codex CLI (via ACP bridge)                      │
│        └──► OpenCode (via ACPx bridge)                     │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│   Native Adapters (LiteLLM / provider SDKs)                │
│   ├── LiteLLMAdapter ──► Claude, GPT, Gemini via API       │
│   ├── ClaudeCodeAdapter ──► Claude Code CLI                │
│   ├── DummyAdapter ──► Deterministic test adapter          │
│   └── HumanAdapter ──► Manual/offline fallback             │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│   IKernelAdapter (canonical interface)                     │
│   └── Unified abstraction for all adapter types             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### ACP Integration (Phase 08)

ACP is integrated into Phase 08 as the **agent discovery and spawning substrate**:

| Component | Description |
|---|---|
| `ACPRegistryAdapter` | Fetches registry JSON, parses agent manifests, handles installation (binary/npx/uvx) |
| `ACPClient` | JSON-RPC 2.0 over stdio, handles initialize, prompt, session/list, session/resume, session/close |
| `IKernelAdapter` enhancements | `spawn_acp_agent`, `list_acp_agents`, `get_acp_registry_adapter`, `is_acp_available` |
| Adapter fallback chain | `OpenClawAdapter → OpenCodeAdapter → LocalLLMAdapter → HumanAdapter` |

### ACP Registry

Forge OS can discover ACP-compatible agents from the official registry:

```
https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
```

Agents in the registry expose:
- **binary** — Platform-specific archives (darwin-aarch64, darwin-x86_64, linux-aarch64, linux-x86_64, windows-*)
- **npx** — Node.js distribution via `npx -y package@latest`
- **uvx** — Python distribution via `uvx package@latest`

### Adapter Principles

- Forge OS Core owns orchestration, gate decisions, state, memory, ADG, and audit logs.
- Adapters only execute agents or translate lifecycle events.
- Adapters must be loaded through configuration or plugin registration.
- Core must never import provider-specific SDKs directly.
- Adapter failure must not corrupt Forge state.
- Adapter results must be normalized before entering Forge Core.
- ACP agents spawned by Forge OS must respect `SecurityEnforcer` policies.

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

ACP-specific capabilities (Phase 08):

- `spawn_acp_agent(agent_id: str, session_id: str) -> ACPClient`
- `list_acp_agents() -> List[AgentManifest]`
- `get_acp_registry_adapter() -> ACPRegistryAdapter`
- `is_acp_available() -> bool`

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
- Can leverage ACPClient for agent communication

Phase:

- Interface can be planned early.
- Full implementation belongs to Phase 11 unless explicitly pulled forward.
- ACP foundation (Phase 08) enables OpenClaw session management.

### 5. OpenCodeAdapter

Purpose:

- Adapter for OpenCode-style execution/runtime flows.
- Can be consumed via ACP (ACPx bridge) or native SDK.

Phase:

- After OpenClawAdapter unless priority changes.

### 6. LocalLLMAdapter

Purpose:

- Local model execution.
- Useful for privacy/offline workflows.
- Serves as the fallback in the ACP adapter chain.

Phase:

- After hosted/runtime adapters.

### 7. HumanAdapter

Purpose:

- Manual/offline fallback where a human performs the agent role.
- Useful for debugging, regulated environments, or no-AI operation.
- Terminal fallback in the adapter chain.

Phase:

- Last in current priority order.
- May be stubbed earlier if needed for interface tests, but full implementation should wait.

## Adapter Fallback Chain

When Forge OS needs to spawn an agent, it attempts adapters in priority order:

```
Agent spawn request
    │
    ▼
LiteLLMAdapter (primary — direct API calls)
    │  (failure or no config)
    ▼
ACPClient → ACPx bridge → Claude Code / Codex / OpenCode
    │  (no ACP bridge available)
    ▼
OpenClawAdapter (Phase 11)
    │
    ▼
LocalLLMAdapter (offline/local models)
    │
    ▼
HumanAdapter (manual fallback)
```

The `SecurityEnforcer` validates all adapter actions regardless of which adapter is used.

## Session Management

ACP introduces session management features (all stabilized April 2026):

| Method | Description |
|---|---|
| `session/list` | Discover existing sessions for history and switching |
| `session/resume` | Reconnect to a session without replaying conversation history |
| `session/close` | Cancel in-flight work and free resources without tearing down the ACP process |
| `session/config/options` | Query available models, modes, and reasoning levels |

Forge OS uses session management for:

- Backtrack rerun with `session resume` (P08.06, P08.33)
- Agent health checks and restart (Phase 09)
- Multi-session coordination (Phase 10 daemon)