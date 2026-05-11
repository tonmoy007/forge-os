# Phase 00 — Foundation and Architecture Lock

## Status

complete

## Objective

Create the authoritative foundation for implementation: runtime decision, schemas, project layout, architecture boundaries, and initial documentation. This phase prevents later confusion and scope drift.

## Scope

Included:

- Runtime/package decision
- Architecture Decision Records
- Core schemas as docs or initial models
- Module/package structure plan
- Interface boundaries
- Test strategy
- Security baseline

Excluded:

- Full CLI implementation
- Agent execution
- Real gates
- Real AI adapters
- Daemon/channel/OpenClaw implementation

## Dependencies

None.

## Resolved Inputs

- Runtime: Python 3.11+.
- Distribution: local Python package first, `pipx` when ready, standalone binary later.
- Adapter priority: `DummyAdapter`, `ClaudeCodeAdapter`, `CodexAdapter`, `OpenClawAdapter`, `OpenCodeAdapter`, `LocalLLMAdapter`, `HumanAdapter`.
- OpenClaw architecture: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.

## Deliverables

1. Runtime decision recorded.
2. Initial `ARCHITECTURE.md`.
3. Initial `SCHEMAS.md`.
4. Initial `IMPLEMENTATION_PLAN.md` or reference to this phase structure.
5. Initial module/package layout decision.
6. Test strategy.
7. Security baseline.
8. ADR directory and first ADRs.

## Tasks

| ID | Task | Output |
|---|---|---|
| P00.01 | Record runtime and package manager decision | ADR |
| P00.02 | Define package/module layout | Architecture doc |
| P00.03 | Define project file layout | Architecture doc |
| P00.04 | Define config schema | Schema doc/model |
| P00.05 | Define pipeline state schema | Schema doc/model |
| P00.06 | Define stage schema | Schema doc/model |
| P00.07 | Define gate schema and result schema | Schema doc/model |
| P00.08 | Define event schema | Schema doc/model |
| P00.09 | Define agent schema | Schema doc/model |
| P00.10 | Define kernel adapter interface | Architecture doc |
| P00.11 | Define artifact and ADG schema placeholders | Schema doc/model |
| P00.12 | Define lesson schema placeholder | Schema doc/model |
| P00.13 | Define tool/security profile placeholder | Schema doc/model |
| P00.14 | Define testing strategy | Test plan |
| P00.15 | Create ADRs for core decisions | `pipeline/decisions/` or project docs |

## Acceptance Criteria

- A developer can start Phase 01 without reading the full original SRS.
- All core data structures have at least draft schemas.
- The adapter boundary is explicit.
- The core-vs-plugin boundary is explicit.
- No provider-specific behavior is required for core operation.
- Any unresolved questions are recorded in `CURRENT_PHASE.md`.

## Exit Checklist

- [x] Runtime selected
- [x] Architecture doc exists
- [x] Schemas doc/models exist
- [x] Initial ADRs exist
- [x] Test strategy exists
- [x] Security baseline exists
- [x] Package/module layout exists
- [x] `CURRENT_PHASE.md` updated to Phase 01 when complete

## Completion Notes

Phase 00 completed as documentation/foundation only. No runtime package, CLI, schemas-as-code, or product behavior was implemented.

Created/updated:

- `ARCHITECTURE.md`
- `SCHEMAS.md`
- `PACKAGE_LAYOUT.md`
- `TEST_STRATEGY.md`
- `SECURITY_BASELINE.md`
- `ADR.md`
- `adr/ADR-001-runtime-and-packaging.md`
- `adr/ADR-002-local-first-core.md`
- `adr/ADR-003-open-formats.md`
- `adr/ADR-004-state-ownership-and-atomic-writes.md`
- `adr/ADR-005-kernel-adapter-boundary.md`
- `adr/ADR-006-optional-layers.md`
- `adr/ADR-007-security-and-human-approval.md`
- `adr/ADR-008-openclaw-boundary.md`

## Suggested Next Prompt

`Implement Phase 00 only. Create the architecture, schema, ADR, and test strategy files. Do not build runtime features yet.`
