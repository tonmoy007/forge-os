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
| `forge_os.adapters` | Kernel adapter interface and implementations | Phase 05 |
| `forge_os.agents` | Agent personas and output contracts | Phase 05 |
| `forge_os.memory` | Reflections, lessons, project/global memory | Phase 06 |
| `forge_os.graphs` | ADG/LKG graph storage and operations | Phase 07 |
| `forge_os.context` | Dependency-aware context building/pruning | Phase 07 |
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

Required capabilities:

- `spawn_agent(persona, context, tools)`.
- `on_event(event, session)`.
- `get_default_tools()`.

Optional capabilities must be discoverable:

- `stop_agent(handle)`.
- `get_status(handle)`.
- `stream_events(handle)`.
- `resume_agent(handle, session)`.

Concrete adapters must normalize provider-specific details before returning results to core.

Adapter implementation order:

1. `DummyAdapter`.
2. `ClaudeCodeAdapter`.
3. `CodexAdapter`.
4. `OpenClawAdapter`.
5. `OpenCodeAdapter`.
6. `LocalLLMAdapter`.
7. `HumanAdapter`.

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
