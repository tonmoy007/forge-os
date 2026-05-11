# Forge OS Build Documentation Index

Use these files to build Forge OS without holding the whole design in memory.

## Core Files

- `BUILD_SPEC.md` — compact product/build specification
- `ARCHITECTURE.md` — Phase 00 architecture baseline
- `SCHEMAS.md` — Phase 00 schema baseline
- `PACKAGE_LAYOUT.md` — package/module layout decision
- `TEST_STRATEGY.md` — testing strategy
- `SECURITY_BASELINE.md` — security and approval baseline
- `ADR.md` — ADR index
- `adr/` — formal Architecture Decision Records
- `IMPLEMENTATION_PLAN.md` — phase index
- `ROADMAP.md` — release roadmap
- `DEFINITION_OF_DONE.md` — completion criteria

## Phase Orchestration

- `plan/ORCHESTRATOR.md` — how to execute phases
- `plan/CURRENT_PHASE.md` — current phase pointer
- `plan/QUESTIONS.md` — unresolved/resolved decisions
- `plan/KERNEL_ADAPTER_INTERFACE.md` — canonical language-agnostic adapter interface
- `plan/ADAPTER_ROADMAP.md` — selected adapter implementation order
- `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md` — OpenClaw integration boundary
- `plan/PHASE_STATUS_TEMPLATE.md` — status update template

## Phase Plans

- `plan/PHASE-00-foundation.md`
- `plan/PHASE-01-cli-scaffold.md`
- `plan/PHASE-02-state-machine.md`
- `plan/PHASE-03-events-hooks.md`
- `plan/PHASE-04-gates-mvp.md`
- `plan/PHASE-05-adapters-agents.md`
- `plan/PHASE-06-memory-lessons.md`
- `plan/PHASE-07-adg-context.md`
- `plan/PHASE-08-backtrack-security.md`
- `plan/PHASE-09-health-global-skills.md`
- `plan/PHASE-10-daemon-dreamer-lazy-context.md`
- `plan/PHASE-11-channels-openclaw-extensions.md`

## Continue Prompt

When ready to implement, use:

`Read BUILD_SPEC.md, plan/CURRENT_PHASE.md, and the current phase file. Implement the current phase only. Update CURRENT_PHASE.md when done.`
