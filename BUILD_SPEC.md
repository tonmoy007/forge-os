# Forge OS Build Spec

This file is the compact source of truth for building Forge OS. The detailed work is split into phase files under `plan/` so each phase can be executed independently without remembering the whole roadmap.

## Product Definition

Forge OS is a standalone, local-first, kernel-agnostic software engineering lifecycle operating system. It orchestrates projects through SDLC stages using deterministic state, quality gates, specialized agents, memory, dependency-aware context, and optional always-on/channel/OpenClaw capabilities.

Forge OS core owns the truth. AI providers, humans, OpenClaw, channels, and plugins are execution surfaces only.

## Non-Negotiable Architecture Rules

1. Core must work offline with `HumanAdapter` or `DummyAdapter`.
2. Project state must be persisted in open formats.
3. Core state must be written only by the orchestration engine.
4. Every component must be replaceable through an interface.
5. Gates must never hang indefinitely; every executable check needs a timeout.
6. Hook, adapter, and agent failures must degrade to warnings unless explicitly configured as blocking.
7. Human approval is required for destructive or high-risk operations.
8. Advanced features are optional layers, not prerequisites for the core CLI.
9. OpenClaw integration must never become a hard dependency.
10. Every automated decision must be auditable.

## Runtime Decision

Selected implementation target: Python 3.11+.

Recommended libraries:

- CLI: `typer`
- Output: `rich`
- Schemas: `pydantic`
- YAML: `pyyaml` or `ruamel.yaml`
- Async HTTP: `aiohttp` (Phase 08+)
- Incremental indexing: in-process mtime+content cache in `context/pruner.py`. CocoIndex was evaluated and **rejected** (lessons.md L004 — requires PostgreSQL, incompatible with local-first design).
- Graphs: `networkx`
- Tests: `pytest`
- Scheduling later: `APScheduler`

## Kernel Adapter Interface

Problem: without a clear abstraction, Forge OS becomes tied to one AI vendor or runtime.

Solution: the Orchestration Engine speaks only to a minimal, language-agnostic `KernelAdapter` interface:

- `spawn_agent(persona: AgentDefinition, context: str, tools: ToolList) -> AgentHandle`
- `on_event(event: LifecycleEvent, session: SessionState) -> EventResponse`
- `get_default_tools() -> ToolList`

Detailed interface notes are tracked in `plan/KERNEL_ADAPTER_INTERFACE.md`.

## Kernel Adapter Priority

Implement adapters in this order:

1. `DummyAdapter`
2. `ClaudeCodeAdapter`
3. `CodexAdapter`
4. `OpenClawAdapter`
5. `OpenCodeAdapter`
6. `LocalLLMAdapter`
7. `HumanAdapter`

Rules:

- `DummyAdapter` comes first for deterministic tests.
- Forge OS core must not import provider-specific SDKs directly.
- Provider adapters must be swappable by configuration.
- OpenClaw is optional and must never become a hard dependency.
- `HumanAdapter` remains a valid offline/manual fallback, but it is not the first real adapter priority.

## Build Layers

Forge OS should be built from the inside out:

1. Schemas and file layout
2. CLI/project scaffolding
3. Deterministic state machine
4. Event bus and hooks
5. Gate system
6. Kernel adapters and agent contracts
7. Memory/reflection/lessons
8. ADG/context pruning
9. Backtrack/security
10. **Async migration, mtime+content cache for incremental indexing, Event Store groundwork (Phase 08.5 — CocoIndex rejected per L004)**
11. Health/global memory/skills
12. Daemon/Dreamer/lazy context
13. Channels/OpenClaw/extensions

## Canonical Project Layout

A Forge-enabled project should contain:

| Path | Purpose |
|---|---|
| `.forge/config.yaml` | Project configuration |
| `.forge/state.json` | Machine-readable pipeline state |
| `.forge/events.jsonl` | Append-only event log |
| `.forge/session-log.jsonl` | Session activity log |
| `.forge/security-audit.jsonl` | Tool/security audit log |
| `.forge/lessons.yaml` | Project lessons store |
| `.forge/reflections/` | Reflections and review notes |
| `.forge/patterns.jsonl` | Skill mining event stream |
| `pipeline/state.md` | Human-readable pipeline state |
| `pipeline/stages.yaml` | Active stage definitions |
| `pipeline/gates.yaml` | Active gate criteria |
| `pipeline/dependencies.graphml` | Artifact Dependency Graph |
| `pipeline/decisions/` | Architecture Decision Records |
| `pipeline/log/` | Daily/health/dream reports |
| `tasks/` | Tasks, plans, lesson summaries |

## Built-In Profiles

### Minimal

1. SRS
2. Build
3. Deploy

### Standard

1. SRS
2. Product
3. Architecture
4. Spec
5. Plan
6. Build
7. Eval
8. Deploy
9. Monitor
10. Feedback
11. Resolve
12. Release

### Expert

Custom stages, custom gates, custom agents, custom profiles, and extension points.

## Required Core Schemas

The initial implementation must define schemas for:

- Project config
- Pipeline state
- Stage definition
- Gate criterion
- Gate result
- Event
- Agent definition
- Kernel adapter handle/result
- Lesson
- Artifact
- Backtrack ticket
- Tool/security profile
- Extension manifest, later phase

## Release Targets

| Release | Purpose | Included Phases |
|---|---|---|
| 0.1 | CLI MVP | Phases 00-04 partial |
| 0.2 | Standard pipeline | Phases 01-05 |
| 0.3 | Agent execution | Phase 05 complete |
| 0.4 | Memory and ADG | Phases 06-07 |
| 0.5 | Quality/security | Phase 08 |
| 1.0 | Stable local Forge OS | Phases 00-09 |
| 1.5 | Always-on Forge OS | Phase 10 |
| 2.0 | Channels/OpenClaw/ecosystem | Phase 11 |

## How To Use The Phase Files

Use `plan/ORCHESTRATOR.md` as the execution guide.

Each phase file contains:

- Objective
- Scope
- Dependencies
- Deliverables
- Tasks
- Acceptance criteria
- Exit checklist
- Suggested next command/prompt

When working, only load this file, the current phase file, and any directly referenced schemas/code. Do not keep the full project plan in working memory.
