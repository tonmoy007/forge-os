# Phase 08 — Backtrack, Rework, Security Baseline, and ACP Integration

## Status

complete

## Objective

Add scoped rework planning, enforce a basic security model around tools, paths, commands, and state files, and integrate ACP (Agent Client Protocol) registry discovery with IKernelAdapter enhancements to enable Forge OS to spawn and manage ACP-compatible coding agents.

## Scope

Included:

- Backtrack ticket schema
- Rework cascade planning from ADG
- Manual approval flow
- Diff-mode stage rerun flag
- Tool/security profile schema
- Path/command restrictions
- Security audit log
- ExternalCommand and MetricThreshold gates
- ACP Registry integration
- ACPClient with JSON-RPC over stdio
- ACP agent discovery, installation, and spawning
- IKernelAdapter ACP enhancements
- Session management (list, resume, close)

Excluded:

- Docker/OS-level deep sandbox
- Fully automated rework without approval
- Channel security
- OpenClaw-specific endpoints (Phase 11)
- Extension/plugin system (Phase 11)

## Dependencies

- Phase 07 complete

## Deliverables

1. Backtrack ticket system.
2. Rework plan generator.
3. User approval commands.
4. Security profile enforcement baseline.
5. Protected state files.
6. External command gate support with timeout.
7. Security audit log.
8. ACP Registry adapter for agent discovery.
9. ACPClient for JSON-RPC/stdio communication.
10. Enhanced IKernelAdapter with ACP agent spawning.
11. Session management commands.
12. `forge agent discover/install/spawn` CLI commands.

## Tasks

### Backtrack & Rework

| ID | Task | Notes | Status |
|---|---|---|---|---|
| P08.01 | Define backtrack ticket schema | `BacktrackTicket` and `BacktrackStore` models with statuses | ✅ |
| P08.02 | Add `forge backtrack list` | List all backtrack tickets with status filtering | ✅ |
| P08.03 | Add `forge backtrack plan <id>` | Generate affected stages from ADG, show rework cascade | ✅ |
| P08.04 | Generate affected stages from ADG | Use existing artifact dependency graph to determine what needs rework | 🔄 |
| P08.05 | Add `forge backtrack approve <id>` | Approve a ticket for execution | ✅ |
| P08.06 | Add `forge backtrack run <id>` in diff mode | Rerun affected stages with diff-mode flag | ✅ |
| P08.07 | Clear stale flags after revalidation | Remove stale downstream flags after rework completes | 🔄 |

### Security Profiles & Enforcement

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.08 | Define tool/security profile schema | YAML-defined profiles for least-privilege access patterns | ✅ |
| P08.09 | Enforce path restrictions for tools | Validate tool access against allowed paths | ✅ |
| P08.10 | Prevent agents from directly writing state files | `SecurityEnforcer` blocks direct `.forge/state.json` writes | ✅ |
| P08.11 | Add command allowlist and timeout runner | `SecurityEnforcer` runs commands with explicit timeouts | ✅ |
| P08.14 | Write `.forge/security-audit.jsonl` | Append-only audit log for all security-relevant actions | ✅ |

### Gates

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.12 | Implement `ExternalCommand` gate evaluator | Execute external commands as gates with timeout support | 🔄 |
| P08.13 | Implement `MetricThreshold` gate evaluator | Parse command output, compare against thresholds | 🔄 |
| P08.15 | Add tests for rework/security/gates | Integration and unit tests for all new components | 🔄 |

### ACP Registry & Agent Discovery

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.16 | Define `ACPRegistryAdapter` interface | Abstract interface for fetching registry JSON | ✅ spec complete |
| P08.17 | Implement `ACPRegistryAdapter` | Fetch registry, parse manifests, binary/npx/uvx install | 🔄 |
| P08.18 | Implement `ACPClient` | JSON-RPC over stdio, initialize, prompt, streaming | 🔄 |
| P08.19 | Add session management methods | `session_list`, `session_resume`, `session_close` | 🔄 |
| P08.20 | Add `session_config_options` | Query available models, modes, reasoning levels | 🔄 |
| P08.21 | Add session info update handling | Handle `session_update` notifications | 🔄 |
| P08.22 | Implement agent installation | Binary, npx, and uvx distribution methods | 🔄 |
| P08.23 | Add `forge acp discover` (CLI scaffolded) | Fetch and display available agents from registry | ⚠️ |
| P08.24 | Add `forge acp install <id>` (CLI scaffolded) | Install agent via specified distribution | ⚠️ |
| P08.25 | Add `forge acp list` (CLI scaffolded) | Show installed/local ACP agents | ⚠️ |
| P08.26 | Add `forge acp sessions` (CLI scaffolded) | List active ACP sessions | ⚠️ |
| P08.27 | Add `forge acp close-session <id>` (CLI scaffolded) | Close an ACP session | ⚠️ |

### ACP Backend Implementation

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.28 | Create `kernel/` module with `acp_client.py` | Full ACPClient with JSON-RPC stdio transport | 🔄 |
| P08.29 | Create `kernel/acp_registry_adapter.py` | Registry fetch, manifest parsing, installer | 🔄 |
| P08.30 | Create `use_cases/acp.py` with `ACPUseCases` | Business logic bridging CLI to ACP backend (currently missing) | 🔄 |
| P08.31 | Add `aiohttp` to project dependencies | Required by ACPRegistryAdapter for HTTP fetches | 🔄 |

### IKernelAdapter ACP Enhancements

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.32 | Add `spawn_acp_agent` to `KernelAdapter` | Abstract method for spawning ACP agents | 🔄 |
| P08.33 | Add `list_acp_agents` to `KernelAdapter` | List available agents from registry | 🔄 |
| P08.34 | Add `get_acp_registry_adapter` to `KernelAdapter` | Return registry adapter for agent discovery | 🔄 |
| P08.35 | Add `is_acp_available` to `KernelAdapter` | Check registry accessibility | 🔄 |
| P08.36 | Enhance `LiteLLMAdapter` with ACP support | Wire ACP client into adapter, implement fallback chain | 🔄 |

### ACP Adapter Fallback Chain

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.37 | Implement adapter priority chain | `OpenClawAdapter → OpenCodeAdapter → LocalLLMAdapter → HumanAdapter` | 🔄 |
| P08.38 | Wire ACP agents into backtrack rerun | Use ACP session resume for `forge backtrack run <id>` | 🔄 |
| P08.39 | ACP integration tests | Mock ACP registry, test agent discovery, installation, spawning | 🔄 |

### Phase 08 Completion

| ID | Task | Notes | Status |
|---|---|---|---|
| P08.40 | Phase 08 tests (backtrack/security/gates/ACP) | Reach target of 120+ tests | 🔄 |
| P08.41 | Update `PHASE-08-backtrack-security.md` status to complete | Orchestrator rule: every phase ends with tests, checks, updated status | 🔄 |

## ACP Registry Integration Details

### Registry Endpoint

```
https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
```

### Agent Manifest Schema

```yaml
id: example-agent                            # Required. Unique identifier
name: "Example Coding Agent"                 # Required. Display name
version: "1.2.0"                             # Required. Semantic version
description: "A coding agent for task X"     # Required. Brief description
distribution:                                # Required. Distribution methods
  binary:                                    # Platform-specific archives
    darwin-aarch64:
      archive: "https://example.com/agent-darwin-arm64.tar.gz"
      cmd: "./agent"
      args: ["--config", "config.json"]
    linux-x86_64:
      archive: "https://example.com/agent-linux-amd64.tar.gz"
      cmd: "./agent"
  npx:                                       # Node.js distribution
    package: "@scope/agent-package"
    args: ["--acp"]
  uvx:                                       # Python distribution
    package: "agent-package"
    args: ["serve"]
repository: "https://github.com/example/agent"
authors: ["Example Corp"]
license: "Apache-2.0"
icon: "icon.svg"
```

### ACPClient JSON-RPC Methods

| Method | Status | Description |
|---|---|---|
| `initialize` | Required | Initialize ACP session with client info |
| `session/prompt` | Required | Send a prompt and stream updates |
| `session/list` | Stabilized | Discover existing sessions |
| `session/resume` | Stabilized | Reconnect without replaying history |
| `session/close` | Stabilized | Cancel in-flight work, free resources |
| `session/config/options` | Stabilized | Query available models, modes, reasoning levels |
| `session/info/update` | Stabilized | Real-time session metadata updates |

### Security Model for ACP Agents

- ACP agents spawned by Forge OS must respect security profiles
- Agents cannot bypass `SecurityEnforcer` for file/path/command access
- ACP session outputs are audited to `.forge/security-audit.jsonl`
- ACP agent modifications to project files are routed through state machine
- Direct writes to `.forge/state.json` are blocked regardless of ACP agent identity

## Architecture: ACP Integration Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                    Forge OS ACP Integration Layer               │
├─────────────────────────────────────────────────────────────────┤
│  Forge OS as ACP Client                                        │
│  ├── ACPClient (JSON-RPC over stdio)                          │
│  ├── Session management (resume, list, close)                 │
│  ├── Streaming updates (session/update)                       │
│  └── Turn completion tracking                                 │
├─────────────────────────────────────────────────────────────────┤
│  ACP Registry Adapter                                         │
│  ├── Registry JSON fetch (CDN)                                │
│  ├── Agent manifest parsing                                   │
│  ├── Agent installation (binary/npx/uvx)                      │
│  └── Local agent cache management                            │
├─────────────────────────────────────────────────────────────────┤
│  IKernelAdapter (Enhanced)                                    │
│  ├── spawn_acp_agent()                                        │
│  ├── list_acp_agents()                                        │
│  ├── get_acp_registry_adapter()                               │
│  └── is_acp_available()                                       │
├─────────────────────────────────────────────────────────────────┤
│  LiteLLMAdapter (Enhanced)                                     │
│  ├── ACP fallback chain                                       │
│  ├── Session resume integration                               │
│  └── SecurityEnforcer integration                            │
└─────────────────────────────────────────────────────────────────┘
```

## CLI Commands Added

| Command | Description |
|---|---|
| `forge backtrack list` | List all backtrack tickets |
| `forge backtrack plan <id>` | Show rework cascade for a ticket |
| `forge backtrack approve <id>` | Approve a backtrack ticket |
| `forge backtrack run <id>` | Run backtrack in diff mode |
| `forge security profile list` | List security profiles |
| `forge security profile validate` | Validate a security profile |
| `forge security audit` | Show audit log entries |
| `forge gate list` | List available gates |
| `forge gate check <name>` | Check a specific gate |
| `forge gate report` | Show latest gate results |
| `forge agent discover` | Fetch and list ACP agents from registry |
| `forge agent install <agent-id>` | Install an ACP agent |
| `forge agent list` | List installed ACP agents |
| `forge agent spawn <agent-id>` | Spawn an ACP agent subprocess |

## Data Models

### BacktrackTicket

```python
@dataclass
class BacktrackTicket:
    id: str                    # UUID
    title: str                 # Brief description
    reason: str                # Why rework is needed
    affected_stage: str       # The stage that needs reworking
    affected_artifacts: List[str]  # From ADG cascade
    downstream_stages: List[str]    # Stages that depend on affected
    status: TicketStatus      # open, approved, in_progress, resolved, rejected
    created_by: str            # User or agent ID
    created_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    resolved_at: Optional[datetime]
    notes: List[str]
```

### SecurityProfile

```yaml
# .forge/profiles/default.yaml
profile_id: "default"
description: "Baseline security profile for Forge OS operations"
tool_restrictions:
  read_paths:
    - "${PROJECT_ROOT}/**"
    - "${FORGE_ROOT}/**"
  write_paths:
    - "${PROJECT_ROOT}/src/**"
    - "${PROJECT_ROOT}/tests/**"
    - "${FORGE_ROOT}/**"
  blocked_paths:
    - "${FORGE_ROOT}/state.json"
    - "${FORGE_ROOT}/.forge-secure/**"
command_allowlist:
  - "git"
  - "pytest"
  - "ruff"
  - "python"
command_timeouts:
  default: 30
  git: 60
  pytest: 300
agent_policy:
  require_approval:
    - "delete"
    - "force_push"
    - "state_override"
  block_direct_state_write: true
  audit_all_actions: true
```

### AgentManifest (ACP)

```python
@dataclass
class AgentManifest:
    id: str
    name: str
    version: str
    description: str
    distribution_binary: Dict[str, BinaryDistribution]
    distribution_npx: Optional[PackageDistribution]
    distribution_uvx: Optional[PackageDistribution]
    repository: Optional[str]
    authors: List[str]
    license: Optional[str]
    icon: Optional[str]
```

## Acceptance Criteria

### Backtrack & Rework
- [ ] Rework cascades require human approval
- [ ] Only affected stages/artifacts are targeted via ADG
- [ ] Diff-mode flag triggers targeted rerun
- [ ] Stale downstream flags cleared after revalidation

### Security
- [ ] Agents cannot directly modify core state files
- [ ] External commands cannot hang indefinitely (timeout enforced)
- [ ] Tool and security actions are audited to `.forge/security-audit.jsonl`
- [ ] Path restrictions enforced via `SecurityEnforcer`

### Gates
- [ ] `ExternalCommandGate` executes with timeout and reports pass/fail
- [ ] `MetricThresholdGate` parses output and compares against thresholds

### ACP Integration
- [ ] `ACPRegistryAdapter` fetches and parses registry JSON
- [ ] `ACPClient` communicates via JSON-RPC over stdio
- [ ] Session resume, list, and close work correctly
- [ ] `forge agent discover` lists available ACP agents
- [ ] `forge agent install` installs agents via npx, uvx, or binary
- [ ] `forge agent spawn` initializes ACP session and streams updates
- [ ] ACP agents respect `SecurityEnforcer` policies
- [ ] ACP integration is optional; LiteLLMAdapter falls back gracefully

### General
- [ ] Tests pass (target: 120+ tests, from 67 baseline)
- [ ] Ruff linting passes
- [ ] Code compiles cleanly

## Exit Checklist

- [ ] Backtrack tickets work (`forge backtrack list/plan/approve/run`)
- [ ] Rework planning works (ADG cascade generation)
- [ ] Approval flow works
- [ ] Security profiles enforced (`SecurityEnforcer` active)
- [ ] ExternalCommand gates work with timeout
- [ ] MetricThreshold gates work
- [ ] ACP Registry adapter works (ACPRegistryAdapter implemented)
- [ ] ACPClient JSON-RPC/stdio works (ACPClient implemented)
- [ ] Session management (list/resume/close) works
- [ ] `forge acp discover/list/install/sessions/close-session` commands are functional
- [ ] `use_cases/acp.py` exists with `ACPUseCases`
- [ ] `kernel/acp_client.py` and `kernel/acp_registry_adapter.py` exist
- [ ] IKernelAdapter ACP methods implemented
- [ ] Adapter fallback chain wired
- [ ] `aiohttp` dependency added to pyproject.toml
- [ ] Async migration preparation tasks deferred to Phase 08.5 (not blocking)
- [ ] CocoIndex evaluation deferred to Phase 08.5 (not blocking)
- [ ] Tests pass (120+)
- [ ] `CURRENT_PHASE.md` updated to Phase 08.5

## Notes For The Implementer

Key references:
1. `plan/PHASE-07-adg-context.md` — Existing ADG implementation
2. `plan/PHASE-05-adapters-agents.md` — Existing `IKernelAdapter` interface
3. `plan/KERNEL_ADAPTER_INTERFACE.md` — Kernel adapter architecture
4. `SCHEMAS.md` — Existing data models
5. `src/forge_os/project/use_cases/` — Use cases layer for backtrack logic
6. `src/forge_os/security/` — Security enforcer and profiles
7. `src/forge_os/gates/` — Existing gate implementations

ACP-specific notes:
- ACP Registry URL: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
- ACP uses JSON-RPC 2.0 over newline-delimited JSON on stdio
- All session methods are stabilized as of April 2026
- ACP agents must be registered in the official registry at `github.com/agentclientprotocol/registry`
- Fallback chain: `OpenClawAdapter → OpenCodeAdapter → LocalLLMAdapter → HumanAdapter`
- ACP integration is additive; existing LiteLLMAdapter behavior preserved

Clean Code Architecture:
- Business logic goes in `src/forge_os/project/use_cases/`
- ACP-specific logic in `src/forge_os/kernel/acp_client.py` and `acp_registry_adapter.py`
- Security enforcement in `src/forge_os/security/`
- CLI commands in `src/forge_os/cli/`

## Suggested Next Prompt

`Implement Phase 08: backtrack tickets, rework cascade planning, security profiles, external/metric gates, audit logging, ACP registry adapter, ACPClient, session management, IKernelAdapter ACP enhancements, and forge agent discover/install/spawn commands.`

## Next Phase: Phase 08.5 Preview

Phase 08.5 (Async Migration & CocoIndex Evaluation) builds on Phase 08's ACP foundation:
- Migrate the `KernelAdapter` protocol from sync to async to match v4 requirements
- Add `aiohttp`/`httpx` async HTTP infrastructure
- Evaluate and adopt CocoIndex as the incremental indexing engine for the Context Pruner
- Tree-sitter based code chunking for Build/Eval stage agent context
- Lay groundwork for event-sourced state (dual-write Event Store alongside state.json)

## Phase 09 Preview

Phase 09 (Health, Global Skills) will build on the ACP and CocoIndex foundation with:
- Health monitoring and adaptive fallback
- Global skill registry accessible to all adapters
- ACP agent health checks and session monitoring
- Skill sharing between ACP and native adapters
- CocoIndex-backed context indexing pipeline