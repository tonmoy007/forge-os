# Phase 09 — Health, Global Memory, and Skill Mining

## Status

not-started

## Objective

Prepare Forge OS for v1 stability by adding health checks, global cross-project memory, profile adaptation, and approved skill mining.

## Scope

Included:

- `forge health check`
- Hook tests
- Gate simulations
- Knowledge integrity checks
- Token budget report
- Global memory directory
- Global lesson promotion
- Project profiles memory
- Pattern tracking
- Skill proposal and approval

Excluded:

- Scheduled daemon health checks
- Dreamer cycle
- Extension registry

## Dependencies

- Phase 08 complete

## Deliverables

1. Health check command.
2. Golden good/bad artifacts for gate simulations.
3. Knowledge integrity scanner.
4. Global memory under `~/.forge/`.
5. Global lesson promotion with approval.
6. Pattern tracker.
7. Skill proposal/approval/install commands.

## Tasks

| ID | Task |
|---|---|
| P09.01 | Implement `forge health check` |
| P09.02 | Add hook unit test harness |
| P09.03 | Add gate simulation fixtures |
| P09.04 | Run known-good/known-bad gate simulations |
| P09.05 | Scan lessons for missing artifact references |
| P09.06 | Scan lessons for conflicts/duplicates, basic deterministic rules |
| P09.07 | Report token budget overages |
| P09.08 | Create global Forge directory |
| P09.09 | Implement global lesson store |
| P09.10 | Track lesson usage by project |
| P09.11 | Suggest promotion after 3 projects |
| P09.12 | Add global promotion approval |
| P09.13 | Implement project profile memory |
| P09.14 | Track repeated action patterns |
| P09.15 | Propose skills after threshold |
| P09.16 | Add skill approval/install/list/run basics |
| P09.17 | Add health/global/skill tests |

## Acceptance Criteria

- Health check produces actionable reports.
- Known-good fixtures pass and known-bad fixtures fail.
- Broken hooks/gates are detected without crashing.
- Global lessons require approval before promotion.
- Skills require approval before installation.
- Rejected skill proposals are not repeatedly suggested.

## Exit Checklist

- [ ] Health check works
- [ ] Gate simulations work
- [ ] Knowledge scan works
- [ ] Global memory works
- [ ] Skill mining approval works
- [ ] Tests pass
- [ ] Local v1 definition of done reviewed
- [ ] `CURRENT_PHASE.md` updated to Phase 10

## Suggested Next Prompt

`Implement Phase 09 only: health checks, gate simulations, global memory, project profiles, and approved skill mining.`
