# Forge OS Architecture

Status: Phase 00 foundation baseline.

Forge OS is a standalone, local-first, kernel-agnostic software engineering lifecycle operating system. It coordinates projects through deterministic state, quality gates, lifecycle events, agent/runtime adapters, memory, artifact dependency context, and optional always-on/channel/OpenClaw integrations.

Forge OS core owns truth. AI providers, humans, OpenClaw, channels, and plugins are execution surfaces only.

## Architectural Goals

1. Keep the orchestration engine deterministic.
2. Persist project state in open, inspectable formats.
3. Keep AI/runtime providers replaceable through the `KernelAdapter` boundary.
4. Support no-AI/manual operation through offline-capable adapters.
5. Make every state transition auditable.
6. Make advanced features optional layers rather than core prerequisites.
7. Keep destructive or high-risk operations behind human approval.

## Runtime and Distribution

- Runtime: Python 3.11+.
- Initial distribution: local Python package.
- Preferred development package manager: `uv`, while preserving standard `pip` compatibility.
- Public installation target after packaging stabilizes: `pipx`.
- Standalone binaries: deferred.
- Async HTTP: `aiohttp` for ACP registry fetches and CocoIndex connectivity (Phase 08.5).
- Incremental indexing: `cocoindex` (optional) for production Context Pruner (Phase 08.5).

Detailed package layout decisions are tracked in `PACKAGE_LAYOUT.md`.

## Core System Boundaries

### Forge OS Core

Forge OS Core owns:

- Project configuration validation.
- Pipeline state and stage transitions.
- Event emission and lifecycle coordination.
- Gate evaluation and gate decisions.
- State persistence and human-readable mirrors.
- Memory/lesson acceptance decisions.
- Artifact dependency graph decisions.
- Backtrack/rework decisions.
- Security policy and audit trail.

### Execution Surfaces

Execution surfaces may perform work, translate events, or propose results. They do not own canonical state.

Execution surfaces include:

- AI provider adapters.
- `DummyAdapter`.
- `HumanAdapter`.
- OpenClaw through `OpenClawAdapter`.
- Hooks.
- Channels.
- Plugins/extensions.

## Package-Level Module Plan

The implementation package should use import package `forge_os`.

| Module | Responsibility | Earliest Phase |
|---|---|---|
| `forge_os.cli` | CLI command definitions and terminal output | Phase 01 |
| `forge_os.config` | Config loading, defaults, and validation | Phase 01 |
| `forge_os.project` | Project discovery and file layout helpers | Phase 01 |
| `forge_os.schemas` | Pydantic schema models matching `SCHEMAS.md` | Phase 01+ |
| `forge_os.core` | Orchestration and canonical state ownership | Phase 02 |
| `forge_os.pipeline` | Stage profiles, transitions, pipeline definitions | Phase 02 |
| `forge_os.events` | Lifecycle events and event bus | Phase 03 |
| `forge_os.hooks` | Hook registration, policy, execution | Phase 03 |
| `forge_os.gates` | Gate criteria, runners, reports | Phase 04 |
| `forge_os.adapters` | Kernel adapter interface and implementations (sync + async from Phase 08.5) | Phase 05 |
| `forge_os.agents` | Agent personas and output contracts | Phase 05 |
| `forge_os.memory` | Reflections, lessons, project/global memory | Phase 06 |
| `forge_os.graphs` | ADG/LKG graph storage and operations | Phase 07 |
| `forge_os.context` | Dependency-aware context building/pruning (CocoIndex-backed from Phase 08.5) | Phase 07 |
| `forge_os.kernel` | ACPClient, ACPRegistryAdapter, async HTTP utilities | Phase 08 |
| `forge_os.backtrack` | Rework/backtrack ticket flows | Phase 08 |
| `forge_os.security` | Tool profiles, approvals, audit logging | Phase 08 |
| `forge_os.health` | Self-tests, diagnostics, health reports | Phase 09 |
| `forge_os.daemon` | Optional background daemon | Phase 10 |
| `forge_os.channels` | Optional channel adapters | Phase 11 |
| `forge_os.plugins` | Optional extension system | Phase 11 |

## Canonical Forge Project Layout

A Forge-enabled project should contain the following files and directories.

| Path | Source of Truth? | Purpose |
|---|---:|---|
| `.forge/config.yaml` | Yes | Project configuration |
| `.forge/state.json` | Yes | Machine-readable pipeline state |
| `.forge/events.jsonl` | Yes | Append-only lifecycle event log |
| `.forge/session-log.jsonl` | Yes | Session activity log |
| `.forge/security-audit.jsonl` | Yes | Tool/security audit log |
| `.forge/lessons.yaml` | Yes | Accepted project lessons |
| `.forge/reflections/` | Yes | Review notes and reflections |
| `.forge/patterns.jsonl` | Yes | Skill/pattern mining stream |
| `pipeline/state.md` | No | Human-readable state mirror |
| `pipeline/stages.yaml` | Yes | Active stage definitions |
| `pipeline/gates.yaml` | Yes | Active gate criteria |
| `pipeline/dependencies.graphml` | Yes | Artifact Dependency Graph |
| `pipeline/decisions/` | Yes | Project-local ADRs |
| `pipeline/log/` | Generated | Daily, health, dream reports |
| `tasks/` | Mixed | Tasks, plans, lesson summaries |

Human-readable mirrors should be generated from machine state where possible and should not be treated as canonical when a machine-readable source exists.

## State Ownership and Persistence

Canonical state must be written only by Forge OS core state services.

State persistence rules:

1. Validate state before writing.
2. Write atomically using a temporary file plus replace operation.
3. Preserve unknown future-compatible fields where safe.
4. Append auditable events for meaningful state changes.
5. Never advance state because an adapter, hook, or plugin failed.
6. Treat corrupt state as a blocking recovery condition rather than silently overwriting it.

## Lifecycle Overview

The lifecycle is built in phases:

1. A project is initialized with config, stage definitions, gates, and state files.
2. The state machine controls stage transitions.
3. Lifecycle events are emitted around sessions, prompts, stages, gates, hooks, and adapters.
4. Gates decide whether progression is allowed, blocked, warned, or advisory.
5. Adapters can execute agent work through the `KernelAdapter` boundary.
6. Memory and lessons are proposed, reviewed, accepted, deprecated, and reused.
7. The ADG tracks artifacts and staleness.
8. Backtrack flows convert failures into explicit rework tickets.
9. Health checks detect broken configuration, stale knowledge, failing hooks, or drift.
10. Optional daemon/channel/OpenClaw/plugin layers extend the core without owning it.

## Kernel Adapter Boundary

Forge OS core must communicate with agent runtimes through the language-agnostic `KernelAdapter` interface only.

### Synchronous Interface (Phase 05-08)

Current required capabilities:

- `spawn_agent(persona, context, tools)`.
- `on_event(event, session)`.
- `get_default_tools()`.

Optional capabilities must be discoverable:

- `stop_agent(handle)`.
- `get_status(handle)`.
- `stream_events(handle)`.
- `resume_agent(handle, session)`.

Concrete adapters must normalize provider-specific details before returning results to core.

### Asynchronous Interface (Phase 08.5+)

Beginning in Phase 08.5, the adapter layer adds async support:

- All `KernelAdapter` methods gain `async def` variants.
- `ACPClient` and `ACPRegistryAdapter` are natively async.
- `DummyAdapter` is ported to async (coexists with sync version).
- `BaseKernelAdapter` provides default async implementations.

The async migration enables ACP streaming, multi-model routing, and live CocoIndex indexing.

### ACP Integration (Phase 08+)

ACP-compatible agents (Gemini CLI, Copilot CLI, Codex) are accessible through:

- `ACPClient` — JSON-RPC over stdio with initialize, prompt, session management.
- `ACPRegistryAdapter` — Discover agents from the official ACP Registry CDN.
- `spawn_acp_agent()` on `KernelAdapter` — Spawn and manage ACP agents.
- Session management: list, resume, close (all stabilized April 2026).

Adapter implementation order:

1. `DummyAdapter`.
2. `ClaudeCodeAdapter`.
3. `CodexAdapter`.
4. `OpenClawAdapter`.
5. `OpenCodeAdapter`.
6. `LocalLLMAdapter`.
7. `HumanAdapter`.
8. `ACPClient`-wrapped agents (discoverable at runtime via `forge acp discover`).

The canonical interface is defined in `plan/KERNEL_ADAPTER_INTERFACE.md`.

## Gate Architecture

Gates are deterministic checks that evaluate whether a stage or transition may proceed.

Gate rules:

- Gates return normalized statuses: pass, fail, warn, skipped, or error.
- Gates must not hang indefinitely.
- Executable gates require explicit timeout and security policy.
- Gate reports must be auditable and reproducible.
- OpenClaw and other adapters may request gate evaluation, but Forge OS core decides gate results.

## Event and Hook Architecture

Events record lifecycle activity and enable hooks/adapters to respond.

Event rules:

- Events should be append-only once persisted.
- Hook failures degrade to warnings unless explicitly blocking.
- Blocking hooks must fail safe.
- Hooks require timeout policy.
- Events should include enough metadata for auditability without leaking secrets.

### Event Sourcing Evolution (Phase 08.5+)

The current `state.json`-based persistence is gradually evolving toward an event-sourced architecture:

1. **Phase 08-08.5 (dual-write):** Every state write also appends an event to the Event Store. State.json remains authoritative.
2. **Phase 09-10 (authority handover):** Event Store becomes authoritative; state.json becomes a cached projection.
3. **Phase 11+ (event-only):** Direct state.json writes are removed. All state is derived by replaying events.

This gradual approach prevents data loss risk while building toward the SRSv4.1 requirement of an immutable, append-only Event Store (FR-ES-001-006).

## Memory and Learning Boundary

Forge OS memory is controlled by Forge OS core. Agents or external systems may propose lessons, reflections, or pattern candidates, but Forge OS decides what persists.

Memory rules:

- Project memory remains project-local by default.
- Global memory requires explicit acceptance and privacy policy.
- Lessons must support lifecycle states such as proposed, accepted, deprecated, and rejected.
- OpenClaw memory must not overwrite Forge OS memory or state.

## Optional Layer Rules

Daemon, Dreamer, channel adapters, OpenClaw, and plugins are optional layers.

Optional layers must:

1. Be disabled unless configured.
2. Use core interfaces.
3. Preserve state ownership.
4. Degrade safely on failure.
5. Avoid becoming prerequisites for CLI/core operation.

## Security Baseline

Security decisions are tracked in `SECURITY_BASELINE.md`.

Non-negotiable security rules:

- Human approval is required for destructive or high-risk operations.
- Secrets must not be logged.
- Tool capabilities must be least-privilege.
- External execution must have timeouts.
- Plugins and adapters cannot bypass core state ownership.

## Clean Code & Layer Separation

Architecture layer boundaries are enforced throughout every phase:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI LAYER (cli/)                         │
│  Typer commands, Rich formatting, arg parsing only           │
│  NO business logic, NO domain imports                        │
│  delegates to → UseCases                                     │
├─────────────────────────────────────────────────────────────┤
│                    USE CASES LAYER (use_cases/)              │
│  Sole orchestrator between CLI and domain                    │
│  Catches domain exceptions, returns domain objects           │
│  Testable without CLI or network                             │
│  imports from → core/, gates/, project/, context/, kernel/   │
├─────────────────────────────────────────────────────────────┤
│                   DOMAIN / INFRASTRUCTURE                    │
│  core/     - StateManager, atomic writes, transitions        │
│  gates/    - Gate coordinator, evaluators                    │
│  context/  - Artifact registry, ADG, pruning                │
│  project/  - Detection, scaffold, profiles, backtrack        │
│  memory/   - Lessons, reflections                            │
│  kernel/   - ACPClient, ACPRegistryAdapter                   │
│  events/   - Event bus, event log                            │
│  hooks/    - Hook registry                                   │
│  agents/   - Personas, output contracts, executor            │
│  adapters/ - KernelAdapter implementations                   │
├─────────────────────────────────────────────────────────────┤
│                     SCHEMAS LAYER (schemas/)                 │
│  Pure Pydantic models, zero Forge OS imports                 │
│  Shared by all layers above                                  │
└─────────────────────────────────────────────────────────────┘
```

### Layer Rules (Enforced)

1. **CLI never imports domain directly.** `cli/main.py` and `cli/commands/*.py` may only import from `use_cases/`, `config/`, `schemas/`, and `project/detect.py`. Direct imports from `gates/`, `core/` (except `StateError`), `context/`, or `memory/` are violations.

2. **Use cases are the sole bridge.** Every new CLI command must have a corresponding `UseCases` method. Use cases import from domain modules freely but never from CLI.

3. **No upward imports.** Domain modules (`core/`, `gates/`, `context/`, `project/`, `memory/`, `kernel/`, `events/`, `hooks/`, `agents/`, `adapters/`) must never import from `cli/` or `use_cases/`.

4. **Schemas are pure data.** `schemas/*.py` files contain only Pydantic models. No business logic, no infrastructure imports.

### Violation Detection Script

```bash
# Upward import check (domain → CLI is forbidden)
grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/context/ src/forge_os/kernel/ src/forge_os/events/ src/forge_os/hooks/

# Business logic in CLI
grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/
```

## Phase 01 Implementation Guidance

Phase 01 may introduce package scaffolding, config loading, `forge init`, and `forge status` basics.

Phase 01 must not implement:

- Full state machine transitions.
- Real gates.
- Real AI adapters.
- Memory/lessons.
- ADG/context pruning.
- Backtracking.
- Daemon/channels/OpenClaw/plugins.

Future features may appear only as documented interfaces, schemas, or TODOs required by Phase 01.
