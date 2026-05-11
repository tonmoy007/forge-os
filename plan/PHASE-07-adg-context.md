# Phase 07 — Artifact Dependency Graph and Context Pruning

## Status

complete

## Objective

Make context deterministic and dependency-aware using artifact registration, an Artifact Dependency Graph, staleness detection, and token-budgeted pruning.

## Scope

Included:

- Artifact schema
- Artifact registry
- ADG storage
- Dependency traversal
- Staleness detection
- Context pruner
- Token estimation
- Context selection audit logs

Excluded:

- Lazy context builder
- Semantic embeddings
- Automatic rework execution

## Dependencies

- Phase 06 complete

## Deliverables

1. Artifact registry.
2. ADG file creation/update.
3. Downstream staleness detection.
4. Deterministic context pruning.
5. Context selection logs.
6. `forge status` stale artifact display.

## Tasks

| ID | Task |
|---|---|
| P07.01 | Define artifact schema |
| P07.02 | Implement artifact registry |
| P07.03 | Define ADG format, GraphML or JSON |
| P07.04 | Implement ADG builder |
| P07.05 | Register stage outputs as artifacts |
| P07.06 | Track artifact modified timestamps/hashes |
| P07.07 | Detect upstream changes |
| P07.08 | Mark downstream artifacts stale |
| P07.09 | Add stale display to `forge status` |
| P07.10 | Implement spread-activation traversal |
| P07.11 | Implement token estimation |
| P07.12 | Enforce context budget |
| P07.13 | Log selected context for each agent spawn |
| P07.14 | Add graph/pruner tests |

## Acceptance Criteria

- Artifact dependencies are explicit and machine-readable.
- Changing an upstream artifact marks downstream artifacts stale.
- Context selection is deterministic and logged.
- Context stays under configured budget.
- Agent spawning uses pruned context rather than all project files.

## Exit Checklist

- [x] Artifact registry works
- [x] ADG builds and persists
- [x] Staleness detection works
- [x] Context pruning works
- [x] Context audit logs exist
- [x] Tests pass
- [x] `CURRENT_PHASE.md` updated to Phase 08

## Suggested Next Prompt

`Implement Phase 07 only: artifact registry, ADG, staleness detection, and deterministic context pruning.`
