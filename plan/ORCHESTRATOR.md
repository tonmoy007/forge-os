# Forge OS Phase Orchestrator

This directory splits the Forge OS build into independent phase files. The goal is to let an implementer work phase by phase without remembering the full roadmap.

## Current Source Files

- `../BUILD_SPEC.md` — compact source of truth
- `CURRENT_PHASE.md` — current execution pointer
- `PHASE-00-foundation.md` through `PHASE-11-channels-openclaw-extensions.md` — detailed phase plans
- `PHASE-08.5-async-cocoindex.md` — async migration, CocoIndex evaluation, Event Store groundwork
- `KERNEL_ADAPTER_INTERFACE.md` — canonical language-agnostic adapter interface
- `ADAPTER_ROADMAP.md` — selected kernel adapter priority
- `OPENCLAW_ADAPTER_ARCHITECTURE.md` — OpenClaw integration boundary

## Operating Rules

1. Work one phase at a time.
2. Before starting a phase, read only:
   - `../BUILD_SPEC.md`
   - `CURRENT_PHASE.md`
   - The current phase file
   - Existing code/config directly related to that phase
3. Do not implement future-phase features early unless they are required as interfaces/stubs.
4. Every phase must end with:
   - Tests, if code exists
   - Diagnostics/build check, if available
   - Updated `CURRENT_PHASE.md`
   - Notes about incomplete or deferred items
5. Keep core deterministic. AI is an adapter, not the engine.
6. Preserve open file formats and human-readable state.
7. If a requirement is ambiguous, record a question in the phase file or `CURRENT_PHASE.md` instead of guessing.

## Discipline Rules (ALL Phases)

### Rule 1: Commit Per Task
Every logical task gets its own commit. Do not batch unrelated changes into one commit.
- A "task" is one deliverable item from the phase task table.
- Exception: trivial fixes (typos, single-line) may be grouped.
- Commit messages must reference the task ID (e.g. `feat: implement ACPClient (P08.18)`).

### Rule 2: No Fabrication
Never invent file paths, API signatures, or test results.
- If you need a file path, verify it exists with `ls` or `glob` first.
- If you need an API signature, read the source definition.
- If you claim a test passes, you must have run it.
- If you are unsure, say "I don't know" — do not guess.

### Rule 3: Capture Lessons Before Fixing
When the user corrects any mistake:
1. **First** — record the lesson in `tasks/lessons.md` with date, trigger, root cause, and rule.
2. **Second** — fix the code.
3. **Third** — reference the lesson ID in the commit message.
The lesson is more valuable than the fix because it prevents future repetitions.

### Rule 4: Create a Resume Prompt
If work is paused mid-phase or context may be reset:
1. Write a handoff/resume block to `plan/RESUME.md` containing:
   - Current phase and task ID.
   - What has been completed (list of finished items).
   - What is pending (next task to start).
   - Any decisions made that are not yet reflected in code/docs.
   - Any tests that are expected to fail.
2. Save `plan/RESUME.md` before any other action.
The resume prompt must be a valid "Suggested User Prompt To Continue" that can be given to a fresh agent.

### Rule 5: Check Previous Commits and File Changes
Before starting implementation on any task:
1. Run `git log --oneline -10` to see recent commits.
2. Run `git diff HEAD` to see uncommitted changes.
3. Check `plan/RESUME.md` if it exists (previous session may have been interrupted).
4. Check `git status` for any in-progress work from other agents.
5. Only then begin implementation.

## Clean Architecture Rules (Non-Negotiable)

Every phase must enforce these layer boundaries:

### Layer 1 — CLI (`cli/`)
- **MUST NOT** contain business logic, domain calculations, or infrastructure calls.
- **MUST** parse args, call exactly one `UseCases` method, and format output.
- **MUST NOT** import from `adapters/`, `core/` (except `StateError`), `gates/`, `context/`, `memory/` directly.
- **MUST** delegate all decisions to `use_cases/`.
- *Violation example:* `cli/main.py:gate_check` imports `GateCoordinator` directly → must be routed through `GateUseCases`.

### Layer 2 — Use Cases (`use_cases/`)
- **MUST** be the only layer that imports from domain modules (`core/`, `gates/`, `project/`, `context/`, `memory/`, `kernel/`).
- **MUST** return domain objects or serializable dicts — never raw framework types (Typer, Rich).
- **MUST** catch domain exceptions and translate them to meaningful results.
- **MUST** be testable without CLI or network (pure unit tests).

### Layer 3 — Domain / Infrastructure (`core/`, `project/`, `gates/`, etc.)
- **MUST NOT** import from `cli/` or `use_cases/` (no upward imports).
- **MUST** accept primitive types or Pydantic models — never CLI types.
- **MUST** expose exceptions that use_cases can catch.

### Schema Layer (`schemas/`)
- **MUST** contain only Pydantic models — no logic, no imports from other Forge OS modules.
- **MUST** match the canonical schema definitions in `SCHEMAS.md`.

### Violation Detection
Before merging any phase, run:
```
# Lint for upward imports (domain should not know about CLI)
ruff check src --select F811 --quiet
# Verify no business logic in CLI commands
grep -rn "import.*GateCoordinator\|import.*StateManager" src/forge_os/cli/ --include="*.py"
```

## Execution Loop

For each phase:

1. Read current phase.
2. Confirm dependencies are complete.
3. Implement only listed deliverables.
4. Add/update tests.
5. Run checks.
6. Update the phase status.
7. Move `CURRENT_PHASE.md` to the next phase.

## Status Values

Use these values in `CURRENT_PHASE.md` and phase files:

- `not-started`
- `in-progress`
- `blocked`
- `review-needed`
- `complete`

## Phase Index

| Phase | File | Theme |
|---|---|---|
| 00 | `PHASE-00-foundation.md` | Architecture lock, schemas, repository decisions |
| 01 | `PHASE-01-cli-scaffold.md` | CLI, config, init, status, project layout |
| 02 | `PHASE-02-state-machine.md` | Pipeline state machine and transitions |
| 03 | `PHASE-03-events-hooks.md` | Event bus and lifecycle hooks |
| 04 | `PHASE-04-gates-mvp.md` | File and pattern gates |
| 05 | `PHASE-05-adapters-agents.md` | Kernel adapters, personas, output contracts |
| 06 | `PHASE-06-memory-lessons.md` | Reflections, lessons, project memory |
| 07 | `PHASE-07-adg-context.md` | Artifact graph and context pruning |
| 08 | `PHASE-08-backtrack-security.md` | Backtrack, rework, security baseline, ACP integration |
| 08.5 | `PHASE-08.5-async-cocoindex.md` | Async adapter migration, CocoIndex evaluation, Event Store groundwork |
| 09 | `PHASE-09-health-global-skills.md` | Health checks, global memory, skill mining |
| 10 | `PHASE-10-daemon-dreamer-lazy-context.md` | Background daemon, Dreamer, lazy context |
| 11 | `PHASE-11-channels-openclaw-extensions.md` | Channels, OpenClawAdapter, extensions |

## Suggested User Prompt To Continue

Use this prompt whenever you want to continue implementation:

`Read BUILD_SPEC.md, plan/CURRENT_PHASE.md, and the current phase file. Implement the current phase only. Update CURRENT_PHASE.md when done.`
