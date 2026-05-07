# Phase 01 — CLI and Project Scaffolding

## Status

complete

## Objective

Create the first usable local interface: `forge init`, `forge status`, config validation, and project scaffolding.

## Scope

Included:

- CLI skeleton
- Config loading/validation
- Project initialization
- Minimal/standard/expert profile templates
- Human-readable and machine-readable initial state files
- Basic `forge status`
- Basic `forge explain`

Excluded:

- Full state machine enforcement
- Agent spawning
- Real gates beyond generated config/templates
- Event hooks beyond simple file writes

## Dependencies

- Phase 00 complete

## Deliverables

1. CLI entrypoint.
2. `forge init`.
3. `forge status`.
4. `forge config show`.
5. `forge config validate`.
6. Project scaffolding for `.forge/`, `pipeline/`, and `tasks/`.
7. Initial profile templates.

## Tasks

| ID | Task |
|---|---|
| P01.01 | Create package skeleton |
| P01.02 | Add CLI framework |
| P01.03 | Implement config loader |
| P01.04 | Implement config validator |
| P01.05 | Implement project root detection |
| P01.06 | Implement `forge init` wizard/non-interactive mode |
| P01.07 | Scaffold `.forge/config.yaml` |
| P01.08 | Scaffold `.forge/state.json` |
| P01.09 | Scaffold `pipeline/state.md` |
| P01.10 | Scaffold `pipeline/stages.yaml` |
| P01.11 | Scaffold `pipeline/gates.yaml` |
| P01.12 | Scaffold `tasks/` |
| P01.13 | Implement `forge status` read-only output |
| P01.14 | Implement `forge explain <topic>` from built-in docs |
| P01.15 | Add tests for init/status/config validation |

## Acceptance Criteria

- `forge init` creates a valid Forge project.
- `forge status` displays profile, current stage, state version, and next suggested action.
- `forge config validate` catches malformed config.
- No AI/API key is required.
- Generated files are human-readable where required.

## Exit Checklist

- [x] CLI works locally
- [x] Init creates expected directories/files
- [x] Config validates
- [x] Status reads state
- [x] Tests pass
- [x] `CURRENT_PHASE.md` updated to Phase 02

## Completion Notes

Phase 01 completed with a minimal local Python package and CLI scaffold only.

Implemented:

- `pyproject.toml` package metadata and `forge` console script.
- `src/forge_os/` package skeleton.
- `forge init` with non-interactive and interactive options.
- `forge status` read-only project status.
- `forge config show`.
- `forge config validate`.
- `forge explain <topic>` for built-in Phase 01 topics.
- Project root detection.
- Phase 01 Pydantic config/state schema models.
- Built-in minimal, standard, and expert profile templates.
- Project scaffolding for `.forge/`, `pipeline/`, and `tasks/`.
- Phase 01 CLI/package tests.

Deliberately not implemented:

- Full state machine enforcement.
- Stage transition commands.
- Real gate execution.
- Hooks.
- Agent spawning or adapters.
- Memory, ADG, backtracking, daemon, channels, OpenClaw, or plugins.

Validation run:

- `/tmp/forge-os-phase01-venv/bin/python -m pytest` — 10 passed.
- `/tmp/forge-os-phase01-venv/bin/ruff check` — passed.
- `python3 -m compileall src tests` — passed.

## Suggested Next Prompt

`Implement Phase 01 only: CLI scaffold, init, status, config validation, and generated project files.`
