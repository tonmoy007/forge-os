# Phase 06 — Memory, Reflections, and Lessons

## Status

complete

## Objective

Add project-level learning: reflections, structured lessons, confidence, approval workflow, and context injection from approved lessons.

## Scope

Included:

- Project lesson schema
- `.forge/lessons.yaml`
- Reflection storage
- Manual lesson commands
- Lesson extraction flow
- Lesson confidence and tags
- Approval/deprecation
- High-confidence lesson injection

Excluded:

- Full Lessons Knowledge Graph sophistication
- Cross-project global memory
- Dreamer/decay automation
- Semantic duplicate detection

## Dependencies

- Phase 05 complete

## Deliverables

1. Lesson model.
2. Reflection model/storage.
3. Lesson CLI commands.
4. Reflector agent invocation after stage/session stop.
5. Lesson Extractor agent invocation or manual extraction queue.
6. Context injection from approved lessons.

## Tasks

| ID | Task |
|---|---|
| P06.01 | Define lesson schema |
| P06.02 | Implement `.forge/lessons.yaml` store |
| P06.03 | Define reflection schema |
| P06.04 | Store reflections under `.forge/reflections/` |
| P06.05 | Add `forge lesson list` |
| P06.06 | Add `forge lesson add` |
| P06.07 | Add `forge lesson approve <id>` |
| P06.08 | Add `forge lesson deprecate <id>` |
| P06.09 | Add confidence scoring |
| P06.10 | Add applicability tags |
| P06.11 | Run Reflector after Stop/stage completion |
| P06.12 | Run Lesson Extractor after correction signals |
| P06.13 | Add approval queue for inferred lessons |
| P06.14 | Inject approved high-confidence lessons into agent context |
| P06.15 | Add tests for lesson lifecycle |

## Acceptance Criteria

- Lessons can be added, approved, listed, and deprecated.
- Inferred lessons do not affect future prompts until approved.
- Reflections are stored and inspectable.
- Approved high-confidence lessons are available to future agent context.
- Lesson storage remains human-readable.

## Exit Checklist

- [x] Lesson store works
- [x] Reflection store works
- [x] CLI lesson lifecycle works
- [x] Approval workflow works
- [x] Context injection uses approved lessons
- [x] Tests pass
- [x] `CURRENT_PHASE.md` updated to Phase 07

## Suggested Next Prompt

`Implement Phase 06 only: project lessons, reflections, approval workflow, and lesson context injection.`
