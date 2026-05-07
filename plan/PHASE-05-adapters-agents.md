# Phase 05 — Kernel Adapters and Agent Contracts

## Status

complete

## Objective

Make agent execution provider-agnostic by implementing the minimal language-agnostic `KernelAdapter` interface, `DummyAdapter`, agent personas, and output contracts.

## Scope

Included:

- `IKernelAdapter`
- Adapter registry/config selection
- `DummyAdapter`
- Adapter roadmap/config placeholders for future adapters
- Agent definition schema
- 12 stage personas
- 4 cross-stage personas
- Output contract validation
- Agent spawning from stage command

Excluded:

- `ClaudeCodeAdapter`
- `CodexAdapter`
- `OpenClawAdapter`
- `OpenCodeAdapter`
- `LocalLLMAdapter`
- Full `HumanAdapter` implementation unless explicitly pulled forward
- Deep tool sandboxing
- LLM review gates

## Dependencies

- Phase 04 complete

## Deliverables

1. Kernel adapter interface matching `plan/KERNEL_ADAPTER_INTERFACE.md`.
2. Adapter registry.
3. `DummyAdapter`.
4. Adapter priority/config placeholders for `ClaudeCodeAdapter`, `CodexAdapter`, `OpenClawAdapter`, `OpenCodeAdapter`, `LocalLLMAdapter`, and `HumanAdapter`.
5. Agent schema and persona files.
6. Output contracts.
7. Stage-to-agent mapping.
8. Agent execution logs.

## Required Agents

Stage agents:

- Requirements Analyst
- Product Designer
- System Architect
- Spec Writer
- Planner
- Builder
- Evaluator
- DevOps
- Observer
- Triage
- Resolver
- Release Manager

Cross-stage agents:

- Reflector
- Lesson Extractor
- Skill Miner
- Gate Checker

## Tasks

| ID | Task |
|---|---|
| P05.01 | Define adapter interface with `spawn_agent`, `on_event`, and `get_default_tools` |
| P05.02 | Implement adapter registry |
| P05.03 | Implement adapter config selection |
| P05.04 | Implement `DummyAdapter` |
| P05.05 | Add adapter config placeholders in selected priority order |
| P05.06 | Define agent schema |
| P05.07 | Create persona directory |
| P05.08 | Write 12 stage personas |
| P05.09 | Write 4 cross-stage personas |
| P05.10 | Define output contract format |
| P05.11 | Validate agent outputs after stop |
| P05.12 | Connect stage start to agent spawn |
| P05.13 | Store agent logs/results |
| P05.14 | Add tests with `DummyAdapter` |

## Acceptance Criteria

- Core engine does not depend on a specific AI provider.
- Adapter can be swapped by config.
- Dummy adapter can complete a stage in tests.
- Adapter roadmap matches the selected priority: `DummyAdapter`, `ClaudeCodeAdapter`, `CodexAdapter`, `OpenClawAdapter`, `OpenCodeAdapter`, `LocalLLMAdapter`, `HumanAdapter`.
- Every standard stage has a persona and output contract.
- Missing required outputs fail appropriate gates/contracts.

## Exit Checklist

- [x] Adapter interface stable and aligned with `plan/KERNEL_ADAPTER_INTERFACE.md`
- [x] `DummyAdapter` works
- [x] Adapter roadmap/config placeholders match selected priority
- [x] Personas exist
- [x] Output contracts exist
- [x] Stage-to-agent execution works
- [x] Tests pass
- [x] `CURRENT_PHASE.md` updated to Phase 06

## Suggested Next Prompt

`Implement Phase 05 only: kernel adapter interface, DummyAdapter, adapter roadmap/config placeholders, agent personas, output contracts, and stage agent spawning. Do not implement real provider adapters yet.`
