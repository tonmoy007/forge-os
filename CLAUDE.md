# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required Reading Before Implementation

`AGENTS.md` is the canonical agent orchestration guide for this repo and overrides general defaults. Before touching code:

1. `plan/CURRENT_PHASE.md` — the execution pointer (phase, status, validation commands, completed deliverables).
2. `plan/RESUME.md` if it exists — previous session may have been interrupted mid-task.
3. `tasks/lessons.md` — captured lessons (L001-L005). These are non-negotiable rules derived from past mistakes.
4. The current phase file (`plan/PHASE-XX-*.md`) — only the phase you're implementing; do not pre-load future phases.
5. `BUILD_SPEC.md` for product invariants, `ARCHITECTURE.md` for layer rules, `SCHEMAS.md` for data contracts.

Then run `git log --oneline -10`, `git diff HEAD`, `git status` to understand in-progress work before starting.

## Build / Test / Lint Commands

The project uses a `.venv/` virtualenv. Always invoke tools through it (`python` on PATH may not have dependencies):

```bash
# Setup (first time)
pip install -e .[dev]

# Full test suite (baseline 649 passing as of Phase 10)
.venv/bin/python -m pytest

# Single test file / single test
.venv/bin/python -m pytest tests/test_health_phase09.py
.venv/bin/python -m pytest tests/test_health_phase09.py::test_specific_name -xvs

# Lint (line-length 100, rules E F I UP B)
.venv/bin/python -m ruff check src tests

# Compile check (catches syntax errors across the tree)
.venv/bin/python -m compileall src tests

# Build the package
python -m build  # uses hatchling backend
```

`pytest` config from `pyproject.toml`: `pythonpath = ["src"]`, `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`), tests live under `tests/`.

## Architecture (the parts that span multiple files)

Forge OS is a local-first, kernel-agnostic SDLC orchestration CLI. The orchestration engine owns canonical state; AI providers, humans, channels, and plugins are *execution surfaces only*.

### Strict Layer Architecture (enforced)

```
cli/  ──▶  use_cases/  ──▶  core/, gates/, project/, context/, memory/, kernel/, events/, hooks/, agents/, adapters/
                                            │
                                            ▼
                                       schemas/  (pure Pydantic, zero forge_os imports)
```

- **`cli/`** — Typer commands and Rich formatting only. Parses args, calls exactly one `UseCases` method, renders output. Must NOT import `gates/`, `core/` (except `StateError`), `context/`, `memory/`, `kernel/`. New commands go in `cli/commands/<domain>.py` as a Typer sub-app registered via `app.add_typer()` in `main.py`.
- **`use_cases/`** — The sole bridge between CLI and domain. Catches domain exceptions, returns domain objects/dicts (never raw Typer/Rich types). Testable without CLI or network.
- **Domain modules** (`core/`, `project/`, `gates/`, `memory/`, `context/`, `kernel/`, `events/`, `hooks/`, `agents/`, `adapters/`) — must NOT import upward from `cli/` or `use_cases/`. Accept primitives or Pydantic models, raise typed exceptions.
- **`schemas/`** — Pydantic models only. Zero imports from any other `forge_os` module.

Pre-merge violation checks (also documented in `AGENTS.md` §5 and `plan/ORCHESTRATOR.md`):

```bash
# Domain → CLI upward imports (must be empty)
grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/context/ src/forge_os/kernel/ src/forge_os/events/ src/forge_os/hooks/

# CLI → domain direct imports (must be empty except for StateError)
grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/

# Direct state.json access outside core/ (must be empty)
grep -rn "state\.json\|forge_dir" src/forge_os/ --include="*.py" | grep -v "forge_os/core/" | grep -v "__pycache__"
```

Known pre-existing violations (`cli/main.py:29-31`, `cli/commands/_shared.py:19,49`, `project/status.py:20`) are listed in `AGENTS.md` §5 — do not introduce new ones; fix existing ones when you touch surrounding code.

### State Ownership

`StateManager` (`src/forge_os/core/state_manager.py`) is the **only** component that may write `.forge/state.json`. All mutations:

1. Validate via Pydantic schemas before writing.
2. Atomic write (tempfile + replace).
3. Append a corresponding event to `.forge/events.jsonl`.
4. Never advance state because an adapter, hook, or plugin failed.

From Phase 08.5 onward there is also a SQLite Event Store (`events/store.py`) using **dual-write** alongside `state.json`. State.json is still authoritative — the Event Store is being grown toward authority over Phases 09-11 (see `ARCHITECTURE.md` "Event Sourcing Evolution"). Always keep both writes consistent.

### Kernel Adapter Boundary

The orchestration engine talks to AI runtimes only through the language-agnostic `KernelAdapter` interface (`adapters/base.py` sync, `adapters/async_base.py` async). Adapter priority order is `Dummy → ClaudeCode → Codex → OpenClaw → OpenCode → LocalLLM → Human`. Forge OS core must never import provider-specific SDKs directly. ACP-compatible agents (`kernel/acp_client.py`, `kernel/acp_registry_adapter.py`) plug in additively without replacing existing adapters.

### Canonical Project Layout (created by `forge init`)

`.forge/{config.yaml, state.json, events.jsonl, session-log.jsonl, security-audit.jsonl, lessons.yaml, reflections/, patterns.jsonl}` are written by Forge OS core. `pipeline/{stages.yaml, gates.yaml, dependencies.graphml, decisions/, log/}` are project-visible artifacts. See `SCHEMAS.md` for the canonical schema of each.

## Phase-Driven Development

Work proceeds **one phase at a time** in strict order (see `plan/ORCHESTRATOR.md` and the phase index in `AGENTS.md` §2). Do not implement future-phase features early unless they are required as interfaces/stubs. Each phase ends with: tests pass, ruff clean, compileall clean, `CURRENT_PHASE.md` updated, and notes about deferred items.

Current phase: **Phase 10** (Daemon, Dreamer, lazy context). Phases 00-09 complete. See `plan/CURRENT_PHASE.md` for live status.

## Discipline Rules from AGENTS.md (apply to every commit)

These are not generic — they exist because past sessions broke them:

1. **Capture lessons before fixing.** When the user corrects a mistake: add an entry to `tasks/lessons.md` (date, trigger, root cause, rule) **first**, then fix the code, then reference the lesson ID in the commit message. The lesson is more valuable than the fix.
2. **One logical task per commit.** Commit messages must reference the task ID from the phase file (e.g. `feat: implement ACPClient (P08.18)`). Trivial typo/single-line fixes may be grouped.
3. **No fabrication.** Verify file paths with `ls`/`glob`, read source for API signatures, run tests before claiming they pass. If unsure, say "I don't know".
4. **Resume prompt on interruption.** If work is paused mid-phase, write `plan/RESUME.md` (current phase, completed tasks, pending tasks, decisions, expected failing tests) **before** any other action.
5. **Every module needs a test file.** `src/forge_os/foo/bar.py` ⇒ `tests/test_foo_bar.py`.

## Lessons Currently in Force (`tasks/lessons.md`)

- **L001 / L005** — Modules that persist to `~/.forge/` MUST accept `forge_dir: Path | None = None` (default `Path.home() / ".forge"`). Tests pass `tmp_path`. Hardcoding `Path.home()` breaks test isolation. Affects `memory/global_store.py`, `memory/project_profiles.py`, `use_cases/skills.py`.
- **L002** — Never use `l`, `O`, `I` as variable names (ruff `E741`). Use `le`, `a`, etc. in comprehensions.
- **L003** — Local-first SQLite: enable `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` (already applied in `events/store.py`).
- **L004** — Do not adopt dependencies that require a database server, network service, or cloud API. CocoIndex was rejected for this reason; the `context/pruner.py` mtime cache replaces it.

## When Adding a New CLI Command

1. Domain logic → `src/forge_os/<module>/`.
2. Use case method → `src/forge_os/use_cases/<domain>.py` (catches domain exceptions, returns dicts/dataclasses).
3. CLI sub-app → `src/forge_os/cli/commands/<domain>.py` (Typer sub-app; calls only the use case).
4. Register sub-app in `cli/main.py` via `app.add_typer(...)`.
5. Tests for the use case → `tests/test_use_cases_<domain>.py`. CLI tests use Typer's `CliRunner`.
6. If the command needs project state, route through `_shared.py` (and prefer extending `ProjectUseCases` over importing `StateManager` directly — the existing direct import is a pre-existing violation, not a precedent).

## Development Discipline Rules

These are non-negotiable, set by the project owner. Apply to every session.

### Docker-First Validation
- All tests MUST be runnable inside Docker. Before any phase sign-off, run the full test suite in the container, not just on the host.
- Keep `Dockerfile.dev` and/or `docker-compose.yml` up to date with every dependency change.
- "Tests pass on my machine" is not enough. Docker is the reference environment.

### Dependency Freshness
- No stale dependencies. Default to the latest stable release of every library unless a pinned version is explicitly documented in `pyproject.toml` with a reason comment.
- Before any release: run `pip list --outdated` and `pip-audit`. Upgrade or document exceptions.
- New dependency additions require: maintained? popular? license compatible? no server/network requirement? (see L004).

### SRS-Driven Development
- Every task, feature, and bug fix MUST trace to a requirement in `plan/v4/SRSv4.1.md` (or the current SRS version).
- `tasks/todo.md` entries MUST include the SRS requirement ID (e.g., `FR-OE-001`) they satisfy. No ID = no task.
- If a proposed change has no SRS backing: either add the requirement to the SRS (with a version bump) first, or reject the change.

### SRS Document Standards
- Every SRS document MUST contain a `## Changelog` table immediately after the title/metadata block.
- Format: `| Version | Date | Author | Summary |`
- Every version bump requires a new changelog row BEFORE any implementation starts.
- The prose "About this version" section supplements but does not replace the formal changelog table.

### Task Planning Gate
- No task enters `tasks/todo.md` without answering four questions in the plan:
  1. Which SRS requirement does this satisfy?
  2. Which files will be created or modified?
  3. How will correctness be verified (test name / smoke test)?
  4. What could break?
- Single-line trivial fixes may skip this gate. Multi-file or architectural changes may not.

### Document Hygiene
- After every phase completion: update and validate `tasks/todo.md`, `tasks/lessons.md`, and `plan/CURRENT_PHASE.md`.
- No completed items left open. No open items left undocumented.
- Lessons go into `tasks/lessons.md` BEFORE the code fix, never after.

### Git Hygiene
- No stale git references. After merging or closing a branch: `git remote prune origin` + `git branch -d <merged>`.
- Tags must point to signed commits on `main` only.
- Never `git add -A` blindly. Inspect every untracked file in `git status` and decide: commit, add to `.gitignore`, or delete.

### .gitignore Hygiene
- When an untracked file should not be committed: add it to `.gitignore` immediately, in the same commit that introduces the pattern.
- Tool-generated directories (`.omc/`, `.sisyphus/`, `.venv/`, caches) belong in `.gitignore`.
- `.env` files are NEVER committed. `.env.example` with placeholder values is always provided instead.
- Generated outputs (logs, build artifacts, coverage reports) get a `.gitignore` entry before the first commit that produces them.
