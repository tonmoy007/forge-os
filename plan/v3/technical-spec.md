# Forge OS – Technical Specification  
**Version 3.0 – Enterprise‑Ready**  
*Document ID: FORGE‑TS‑3.0*  
*Date: 2026‑05‑07*  
*Status: Final Draft*

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture](#2-architecture)
3. [Component Specifications](#3-component-specifications)
   - 3.1 Orchestration Engine
   - 3.2 Kernel Adapter Layer
   - 3.3 Agent System
   - 3.4 Gate Coordinator
   - 3.5 Memory Subsystem (LKG, ADG, Tiered Memory)
   - 3.6 Context Pruner
   - 3.7 HITL Manager
   - 3.8 Sandbox Manager
   - 3.9 Audit & Observability
   - 3.10 Channel Adapter Layer
   - 3.11 Health Daemon
4. [Data Models](#4-data-models)
5. [Interfaces & Protocols](#5-interfaces--protocols)
6. [Workflows & Lifecycles](#6-workflows--lifecycles)
7. [Security Model](#7-security-model)
8. [Observability & Audit](#8-observability--audit)
9. [Versioning & Evolution](#9-versioning--evolution)
10. [Deployment & Configuration](#10-deployment--configuration)
11. [Appendix A – Gate Type Definitions](#11-appendix-a--gate-type-definitions)
12. [Appendix B – MCP Tool Schemas](#12-appendix-b--mcp-tool-schemas)

---

## 1. Introduction

### 1.1 Purpose
This document provides the complete technical blueprint for Forge OS, a self‑sustaining Software Development Lifecycle (SDLC) ecosystem. It translates the Software Requirements Specification (v3.0) into a concrete, buildable system architecture. Every component, interface, data model, and protocol is defined here to enable deterministic implementation by either human engineers or AI coding assistants.

### 1.2 Scope
The specification covers the entire Forge OS stack:
- Core orchestration engine and 12‑stage pipeline.
- Kernel‑agnostic AI agent hosting via adapters (Claude, GPT, OpenClaw, local).
- Multi‑modal quality gate enforcement with sandboxed execution.
- Graph‑based three‑tier memory and cross‑project learning.
- Structured Human‑in‑the‑Loop governance with risk‑based escalation.
- Immutable audit trail and dual‑stream observability.
- Extensibility through MCP servers and a community plugin ecosystem.

### 1.3 Design Principles
- **Modularity by Contract**: All subsystems communicate via well‑defined interfaces (MCP, REST, gRPC, CLI).
- **Kernel Agnosticism**: The system operates identically regardless of the underlying AI provider.
- **Immutable Record**: Every decision, tool call, and state change is recorded in an append‑only ledger.
- **Progressive Complexity**: The system ships in three profiles (`minimal`, `standard`, `expert`) to allow gradual adoption.
- **Self‑Maintenance**: The system monitors its own health and can propose improvements to itself.

---

## 2. Architecture

### 2.1 High‑Level Block Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    CLI / Web Dashboard                    │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│                Orchestration Engine                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ State Machine│ │Stage Dispatcher│ │ Event Bus    │     │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘     │
│         │                │                │              │
│  ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐     │
│  │ Context Prune│ │ Gate Coord.  │ │ HITL Manager │     │
│  └──────────────┘ └──────────────┘ └──────────────┘     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
│  │ MCP Host     │ │ Audit Logger │ │ Sandbox Mgr  │     │
│  └──────────────┘ └──────────────┘ └──────────────┘     │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│              Kernel Adapter Layer (KAL)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Claude   │ │ GPT      │ │ OpenClaw │ │ Local LLM│   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└────────────────────────┬─────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│              Memory & Knowledge Subsystem                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ LKG      │ │ ADG      │ │ Tier2    │ │ Tier3    │   │
│  │ (Graph)  │ │ (Graph)  │ │ (Project)│ │ (Global) │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└──────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────┐
│          External Services (MCP & Sandbox)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │Memory MCP│ │Code Graph│ │ Test     │ │ Deploy   │   │
│  │(Neo4j/   │ │MCP       │ │ Runner   │ │ MCP      │   │
│  │ SQLite)  │ │          │ │          │ │          │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐                                           │
│  │gVisor    │  (Sandbox Container Runtime)              │
│  └──────────┘                                           │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology Choices |
|-------|-------------------|
| Core Language | Python 3.12+ (for async, type hints) |
| CLI Framework | Click / Typer |
| MCP Library | `mcp` (Python SDK) |
| Graph Storage | Neo4j (standard), Kioku‑Lite/SQLite (embedded) |
| Vector Search | pgvector / Chroma / SQLite‑vec |
| Messaging Bus | Redis (for team deployments) or internal event bus (single‑user) |
| Sandbox Runtime | gVisor `runsc` |
| Observability | OpenTelemetry SDK, Prometheus metrics exporter |
| Audit Ledger | Append‑only JSONL + HMAC chaining (git‑friendly) |
| HITL UI | Terminal UI (Rich) + Web (React, optional) |
| Deployment | PyPI package, Docker images, systemd service |

---

## 3. Component Specifications

### 3.1 Orchestration Engine

- **State Machine**: Finite state automaton with 12 primary stages (plus custom). Transitions governed by gate results. All state is persisted atomically to `pipeline/state.md` (human‑readable) and `.forge/state.json` (machine‑readable).
- **Stage Dispatcher**: Receives `stage.start` command → verifies previous gate → spawns agent → tracks progress → emits `stage.complete` when gate passes.
- **Event Bus**: In‑process pub/sub that fires lifecycle events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd`. Hooks are Python functions registered against these events.

### 3.2 Kernel Adapter Layer (KAL)

- **Abstract Interface** (`IKernelAdapter`):
  - `get_capabilities() → Capabilities` – returns supported tools, agents, MCP servers.
  - `spawn_agent(persona: AgentPersona, context: str, policy: ToolPolicy) → AgentSession`
  - `on_event(event: LifecycleEvent) → Optional[ActionResult]`
  - `sync_memory(session: AgentSession) → List[MemoryDelta]`
- **Reference Implementations**:
  - `LocalLLMAdapter`: Uses a local LLaMA/ChatGLM/OLLAMA process with a lightweight tool‑calling
  - `OpenCodeAdapter`: Use Opencode And MCP to spawn sub-agents
  - `ClaudeCodeAdapter`: Uses Claude Code hooks and MCP to spawn sub‑agents.
  - `OpenCLawAdapter`: Bridges Forge OS to OpenClaw Gateway via REST. wrapper.
- **Tool Policy**: Each agent gets a JSON policy restricting allowed MCP tool names, filesystem paths, and network endpoints.

### 3.3 Agent System

- **Persona Definition** (`agents/<stage>.yaml`):
  - `role`, `goal`, `allowed_tools`, `output_contract` (list of required artifact paths).
  - `system_prompt_template` with placeholders for injected context.
- **Agent Spawner**: Combines persona, pruned context (from Context Pruner), and tool policy; delegates to the active Kernel Adapter.
- **Cross‑stage Agents**: Reflector, Lesson Extractor, Skill Miner, Gate Checker – run as short‑lived sub‑agents triggered by hooks.

### 3.4 Gate Coordinator

- **Gate Criteria Types** (see Appendix A):
  - `FileExistence`, `PatternMatch`, `LLMReview`, `ExternalCommand`, `MetricThreshold`
- **Check Pipeline**: For a stage, all criteria are evaluated in parallel (where possible). Results aggregated into a `GateReport`.
- **Blocking Logic**: If `advance_mode == 'strict'` and any non‑optional criterion fails, advance is blocked (exit code 2). In `warn` mode, only warnings are recorded.
- **External Sandbox**: `ExternalCommand` criteria are executed inside a gVisor container (see Sandbox Manager).

### 3.5 Memory Subsystem

#### 3.5.1 Lessons Knowledge Graph (LKG)
- **Backend**: MCP‑wrapped graph DB. Default: Kioku‑Lite (SQLite embedded). Enterprise: Neo4j MCP server.
- **Nodes**: `Lesson`, `Artifact`, `Stage`, `Project`, `Pattern`
- **Edges**: `DEPENDS_ON`, `CONTRADICTS`, `APPLIES_TO`, `SUPERSEDES`, `EXTRACTED_FROM`
- **Lesson Schema**:
  ```yaml
  id: L-010
  trigger: "Detection of raw hex color in UI file"
  rule: "Always use design token var(--color-*); never raw #RRGGBB."
  confidence: 0.92
  stage_tags: [2, 6]
  last_used: "2026-05-01T12:00:00Z"
  version: 1
  source: extractor
  ```
- **Operations**: `query(stage, tags, min_confidence) → List[Lesson]`, `apply_decay()`, `detect_contradictions()`.

#### 3.5.2 Artifact Dependency Graph (ADG)
- **Backend**: In‑memory `networkx.DiGraph` persisted to GraphML.
- **Nodes**: Artifact (SRS, Product, Architecture, Spec, Plan, Build, etc.).
- **Edges**: `GENERATED_FROM` (upstream → downstream), `INFLUENCES`.
- **Staleness Detection**: When an artifact is modified, a BFS marks all downstream nodes as `status: potentially_stale`. The Context Pruner uses this when deciding what to inject.

#### 3.5.3 Three‑Tier Storage
- **Tier 1 (Session)**: In‑process context window (never persisted directly).
- **Tier 2 (Project)**: `pipeline/` directory, `.forge/lessons.yaml`, `.forge/sessions/`, ADG. Git‑versioned.
- **Tier 3 (Global)**: `~/.forge/global-lessons.md`, `~/.forge/project-profiles.yaml`, `~/.forge/skill-library/`. Promotion from Tier 2 when confidence > 0.8 and used in ≥3 projects.

### 3.6 Context Pruner
- **Algorithm**: 
  1. Parse user request to extract key entities/terms.
  2. Traverse ADG from required stage artifacts outward using BFS.
  3. Score each node by: BM25 relevance to request, graph distance, recency, lesson applicability.
  4. Greedy fill token budget (configurable, default 1800) with full‑text for highest‑scored, skeleton (headings only) for mid‑scored.
  5. If still over budget, apply GraphCompactor summarisation.
- **Lazy Loading**: Initial context contains only a menu of available skills and low‑confidence lessons. Full details are loaded on‑demand when the agent selects them.

### 3.7 HITL Manager
- **Risk Classifier**: Assigns a risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) to each gate based on its type and stage.
  - `LOW`: `FileExistence`, `PatternMatch` → auto‑advance.
  - `MEDIUM`: `LLMReview` → notification, 30‑second override window.
  - `HIGH`: `ExternalCommand`, `MetricThreshold` with production impact → structured checkpoint.
  - `CRITICAL`: Deployment, destructive tool use → Two‑Key Rule.
- **Decision Types**:
  - `phase_gate`: artifact summary + gate results, approve/reject/feedback.
  - `choice`: render options with diffs, user selects one.
  - `feedback`: multi‑question structured form.
- **Enforcement**: Approver identity ≠ initiator identity (Maker‑Checker). Cryptographic signing of decisions.
- **Integration**: Checkpoints rendered via CLI (Rich) or web dashboard; decisions logged immutably.

### 3.8 Sandbox Manager
- **Container Runtime**: gVisor `runsc` for all `ExternalCommand` gates and agent `Bash` calls.
- **Kamikaze Mode**: Container started with empty ephemeral FS, no network egress (except explicit allowlist), memory limit, and auto‑destroyed after command completion (or 30s timeout).
- **Per‑Agent Profiles**: `sandbox.yaml` per stage defines allowed commands, filesystem paths, environment variables.
- **Credential Proxy**: A sidecar injects `FORGE_SESSION_TOKEN` with scoped permissions; agents have no raw secrets.

### 3.9 Audit & Observability
- **Audit Ledger**: `.forge/audit/ledger.jsonl` – append‑only, each entry:
  ```json
  {
    "entry_id": "uuid",
    "timestamp": "ISO8601",
    "event": "gate_advance | hitl_decision | tool_call | state_change",
    "agent_id": "...",
    "user_id": "...",
    "details": "...",
    "signature": "HMAC(chain_key, entry_hash)"
  }
  ```
- **Dual‑Stream Tracing**:
  - Stream 1: OTel spans from agent loop: LLM API calls, tool invocations, MCP calls.
  - Stream 2: OS‑level events (file access, network connections, process execution) captured via eBPF or `auditd`, correlated by `session_id`.
- **Token Economics Dashboard**: Aggregated metrics exported to Prometheus, showing cost per stage, token waste %, context relevance score.

### 3.10 Channel Adapter Layer
- **Interface**: `send_message(channel_id, message)`, `on_incoming(channel_id, text, sender)`
- **Implementations**: Console (for testing), OpenClaw channels (WhatsApp, Telegram, Discord), custom webhook.
- **Security**: All incoming messages are treated as untrusted; commands are parsed and run through the same permission checks as CLI inputs.

### 3.11 Health Daemon
- **Scheduled Jobs**:
  - Hook unit tests (mock events injected to validate hook scripts).
  - Gate simulations (known‑good/bad artifacts tested).
  - Knowledge integrity scan (LKG contradictions, stale ADG nodes).
  - Token budget audit.
- **Self‑Healing**: Can automatically disable a failing hook, mark a lesson dormant, or archive a rarely‑used skill, with notification.

---

## 4. Data Models

### 4.1 Pipeline State (`pipeline/state.md` frontmatter)
```yaml
project: "my-app"
cycle: "feature-login"
current_stage: 6
task_id: "T-007"
gate_status: passed
last_reflection: "..."
active_lessons: ["L-010", "L-015"]
created: "2026-05-01T09:00:00Z"
updated: "2026-05-01T16:20:00Z"
```

### 4.2 Agent Persona
```yaml
name: "System Architect"
allowed_tools: ["Read", "Write", "Grep", "WebSearch"]
forbidden_tools: ["Bash", "Network"]
output_artifacts:
  - "pipeline/03-architecture/architecture.md"
  - "pipeline/03-architecture/c4-diagrams.md"
system_prompt: "..."
```

### 4.3 Gate Criteria
```yaml
gates:
  stage_6:
    - id: "test_coverage"
      type: "MetricThreshold"
      command: "pytest --cov --cov-report=json"
      metric: "coverage_percent"
      threshold: 80
      risk: HIGH
    - id: "no_raw_css"
      type: "PatternMatch"
      pattern: "#[0-9a-fA-F]{3,8}(?!\\s*var)"
      files: "*.tsx, *.css"
      risk: LOW
```

### 4.4 Lesson (LKG Node)
```json
{
  "id": "L-010",
  "type": "Lesson",
  "properties": {
    "trigger": "Use of raw hex colors",
    "rule": "Always use design tokens",
    "confidence": 0.92,
    "stage_tags": [2, 6, 7],
    "created_at": "2026-04-15",
    "last_used": "2026-05-01",
    "version": 1,
    "source": "extractor"
  }
}
```

### 4.5 Audit Entry
```json
{
  "entry_id": "550e8400...",
  "timestamp": "2026-05-01T16:20:00Z",
  "event": "gate_advance",
  "stage": 6,
  "agent_id": "builder-01",
  "user_id": null,
  "details": {"passed": 5, "failed": 0, "criteria": [...]},
  "signature": "aa9d5f..."
}
```

---

## 5. Interfaces & Protocols

### 5.1 CLI Commands
- `forge init [--template <profile>]`  
- `forge stage start <stage_name>`  
- `forge status`  
- `forge resume`  
- `forge health check`  
- `forge audit query [--stage X] [--risk HIGH]`  
- `forge plug install <name>`  

### 5.2 MCP Tools (exposed by Forge OS to kernels)
- `forge.pipeline.status()`  
- `forge.memory.query_lessons(stage, tags)`  
- `forge.audit.log(event_type, details)`  
- `forge.hitl.request(decision_type, context)`  

### 5.3 Kernel Adapter API (Internal)
```python
class IKernelAdapter(ABC):
    @abstractmethod
    async def spawn_agent(self, persona: AgentPersona, context: str, policy: ToolPolicy) -> AgentSession: ...

    @abstractmethod
    async def get_capabilities(self) -> Capabilities: ...

    @abstractmethod
    async def on_event(self, event: LifecycleEvent) -> Optional[EventResponse]: ...
```

### 5.4 Event Definitions
Events are JSON objects published on the event bus:
```json
{
  "type": "PreToolUse",
  "session_id": "...",
  "tool_name": "Write",
  "tool_input": {"path": "...", "content": "..."},
  "agent_id": "..."
}
```

### 5.5 Channel Adapter Interface
```python
async def send_message(channel_id: str, message: str, format: str = "markdown")
async def on_incoming(channel_id: str, text: str, sender_id: str)
```

---

## 6. Workflows & Lifecycles

### 6.1 Session Lifecycle
1. `SessionStart` → load state, inject context (Context Pruner).
2. User input → `UserPromptSubmit` hook parses intent, possibly triggers stage transition.
3. If stage transition, Gate Checker runs on previous stage. If passed, dispatcher spawns agent.
4. Agent work → `PreToolUse`/`PostToolUse` hooks enforce design system, log decisions.
5. `Stop` → Reflector runs, Lesson Extractor scans transcript, Gate Checker runs again.
6. `SessionEnd` → final state persist, memory sync to Tier 2.

### 6.2 Backtrack and Rework
1. Feedback (Stage 10) or Resolve (Stage 11) identifies flaw in earlier artifact.
2. ADG analysis determines all downstream artifacts affected.
3. Backtrack ticket created with rework cascade.
4. User approves; system re‑opens earliest affected stage, spawns its agent with “diff mode” context.
5. Gates re‑evaluated only for changed artifacts.

### 6.3 Dreamer Cycle (Nightly)
1. Daemon triggers Dreamer agent.
2. Agent reads all daily session digests and recent reflections.
3. Re‑ingests old decisions and checks for contradictions via LKG queries.
4. Applies decay function to lessons, marks dormant if below threshold.
5. Generates morning report and, if configured, proposes lesson merges/retirements.

### 6.4 Skill Mining & Evolution
1. Pattern tracker aggregates tool‑call sequences across sessions.
2. When frequency ≥ 3, Skill Miner generates a `SKILL.md` and optionally a small MCP server scaffolding.
3. User approves → skill installed in `.claude/skills/` (or global library).
4. Health Daemon monitors skill usage; if unused for 90 days, skill is deprecated.

---

## 7. Security Model

### 7.1 Phase‑Based Access Control
- **Contract Writers** (Stages 1‑5): can `Read`/`Write` artifacts in `pipeline/01‑05/`, no `Bash`, no access to source code.
- **Implementers** (Stage 6): can `Read`/`Write` source code and run sandboxed `Bash`, cannot modify `pipeline/01‑05/` or design system.
- **Validators** (Stage 7): read‑only across all artifacts; can run `ExternalCommand` gates.

### 7.2 Sandbox Policies (gVisor)
- Container spec:
  - CPU: max 1 core, Memory: 512MB
  - No network devices (unless allowlist specified)
  - Mounts: ephemeral `/workspace`, read‑only pipeline artifacts if needed.
  - Capabilities: all dropped
  - Timeout: 30s for commands, 300s for test suites.

### 7.3 Credential Management
- Vault‑like sidecar supplies short‑lived `FORGE_SESSION_TOKEN` to agent containers.
- Token scoped to project, stage, and allowed operations.
- No secrets in environment variables visible to agent.

### 7.4 Prompt Integrity
- All user feedback and channel messages are wrapped in `<forge-message source="external" trust="untrusted">...</forge-message>` to clearly separate zones.

---

## 8. Observability & Audit

### 8.1 Trace Schema (OpenTelemetry)
- Spans:
  - `forge.session` (attributes: project_id, cycle, stage, agent_type)
  - `forge.tool_call` (tool_name, input_hash, output_hash, duration)
  - `forge.gate_check` (criterion_id, result, duration)
  - `forge.hitl` (decision_type, approver, outcome)

### 8.2 Metrics (Prometheus)
- `forge_tokens_total{stage, agent}`
- `forge_stage_duration_seconds`
- `forge_lessons_promoted_total`
- `forge_sandbox_violations_total`

### 8.3 Audit Ledger Integrity
- Each entry includes a SHA‑256 hash of previous entry (`chain_key`). The genesis entry is signed with the project’s initial key.
- `forge audit verify` checks the HMAC chain and reports any breaks.

---

## 9. Versioning & Evolution

- **Artifacts**: Each artifact file contains a YAML frontmatter with `version`, `last_updated`, `dependencies` (list of upstream artifact versions).
- **Lessons**: LKG nodes have `version` field; `SUPERSEDES` edge links old versions.
- **Skills**: Skill manifests include semver version and a `success_rate` metric (based on usage outcomes).
- **Pipeline Configuration**: `pipeline/stages.yaml` is versioned; Health Daemon can propose pull requests to adjust gate criteria or stage order.

---

## 10. Deployment & Configuration

### 10.1 Profiles
- `minimal`: 3‑stage pipeline, embedded SQLite memory, no sandbox, no HITL checkpoints (just logs).
- `standard`: 12‑stage pipeline, Neo4j/Kioku‑Lite memory, gVisor sandbox for Stage 6 Bash, HITL for HIGH gates.
- `expert`: Everything enabled, custom stages, full MCP integration, daemon mode.

### 10.2 Configuration Files
- `~/.forge/config.yaml`: user‑level defaults (default kernel, profile, token budget).
- `project/.forge/config.yaml`: project‑level overrides, list of active MCP servers, sandbox policies.

### 10.3 Daemon Mode
- `forge daemon start` – launches a systemd process that runs the Observer and Dreamer agents on a schedule.
- Communicates with the Orchestration Engine via internal gRPC or Unix socket.

---

## 11. Appendix A – Gate Type Definitions

| Type | Description | Example |
|------|-------------|---------|
| `FileExistence` | Checks that a required file exists | `pipeline/03-architecture/architecture.md` must exist |
| `PatternMatch` | Checks that file content does/doesn’t match a regex | No raw hex colors in `.tsx` files |
| `LLMReview` | Asks an LLM (Reflector) to evaluate an artifact against a rubric | “Does architecture document address all SRS items?” |
| `ExternalCommand` | Runs a command (in sandbox) and checks exit code/output | `pytest --exitfirst` must return 0 |
| `MetricThreshold` | Parses command output for a numeric metric and compares | `pytest --cov` coverage >= 80% |

---

## 12. Appendix B – MCP Tool Schemas

### `forge.memory.query_lessons`
```json
{
  "name": "forge.memory.query_lessons",
  "parameters": {
    "stage": "integer",
    "tags": ["string"],
    "min_confidence": "float"
  },
  "returns": "list of lesson objects"
}
```

### `forge.audit.log`
```json
{
  "name": "forge.audit.log",
  "parameters": {
    "event_type": "string",
    "details": "object",
    "session_id": "string"
  },
  "returns": "entry_id"
}
```

### `forge.hitl.request`
```json
{
  "name": "forge.hitl.request",
  "parameters": {
    "decision_type": "phase_gate | choice | feedback",
    "context": "object",
    "risk_level": "string"
  },
  "returns": "decision_id"
}
```

---

**End of Technical Specification**

This document is exhaustive enough for cross‑functional teams to begin implementation in parallel. Each component can be developed, tested, and integrated independently, following the plan detailed in the Implementation Plan.
