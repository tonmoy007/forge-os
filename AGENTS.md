# Forge OS — Agent Orchestration Guide

> **Purpose:** This file tells AI agents and human implementers exactly how to approach the Forge OS codebase, what the current build order is, and conventions to follow.
>
> **2026-05-13 update.** The project is in **strategic pause** pending decisions D4-D8 in `/STATUS.md`. Cross-cutting orchestration + clean architecture + clean code + separation-of-concerns discipline now lives in `plan/PLAYBOOK.md` — read that first, then this file, then `plan/ORCHESTRATOR.md` (phase-mode only).
>
> **BEFORE IMPLEMENTING ANYTHING:** Read `/STATUS.md` (strategic state) → `plan/PLAYBOOK.md` (execution discipline) → `plan/ORCHESTRATOR.md` (phase execution rules, Fork B) → `tasks/lessons.md` (captured lessons from past mistakes).

---

## 0. Discipline Rules (Non-Negotiable)

These rules apply to every session, every phase, every commit. Violations must be called out in code review.

### 0.1 No Fabrication
Never invent file paths, API signatures, or test results.
- Verify file existence with `ls` or `glob` before referencing.
- Read source definitions before calling any API.
- Run tests before claiming they pass.
- If unsure, say "I don't know" — guessing produces bugs.

### 0.2 Capture Lessons Before Fixing
When the user corrects ANY mistake:
1. **First** — write the lesson to `tasks/lessons.md` with date, trigger, root cause.
2. **Second** — fix the code.
3. **Third** — include `Lesson: <id>` in the commit message.
The lesson prevents future repetition. It is more valuable than the fix.

### 0.3 Resume Prompt on Interruption
If a session may be interrupted or context reset:
1. Write `plan/RESUME.md` containing phase, completed tasks, pending tasks, decisions, failing tests.
2. The resume prompt must be a valid instruction a fresh agent can follow to continue.
3. Do this before any other action when interruption is anticipated.

### 0.4 Check History Before Starting
Before implementing any task:
1. `git log --oneline -10` — recent commits.
2. `git diff HEAD` — uncommitted changes.
3. Check `plan/RESUME.md` for interrupted session state.
4. `git status` — detect in-progress work from other agents.
5. Then begin implementation.

---

## 1. Project Identity

**What Forge OS is:**
A local-first, lifecycle-aware software engineering CLI that orchestrates a deterministic 12-stage SDLC pipeline. It enforces quality gates, manages artifact dependencies, learns from past mistakes, and spawns AI agents through a provider-agnostic adapter interface.

**What Forge OS is NOT:**
- Not an IDE plugin
- Not a CI/CD toolchain
- Not an AI wrapper
- Not a package manager

---

## 2. Build Sequence

The project is built phase by phase in strict order. Do not implement future-phase features early.

### Phase Index (in build order)

| # | File | Theme | Status |
|---|------|-------|--------|
| 00 | `plan/PHASE-00-foundation.md` | Architecture lock, schemas, ADRs | ✅ |
| 01 | `plan/PHASE-01-cli-scaffold.md` | CLI, init, status, config | ✅ |
| 02 | `plan/PHASE-02-state-machine.md` | Pipeline state, transitions | ✅ |
| 03 | `plan/PHASE-03-events-hooks.md` | Event bus, hook registry | ✅ |
| 04 | `plan/PHASE-04-gates-mvp.md` | File/pattern gates | ✅ |
| 05 | `plan/PHASE-05-adapters-agents.md` | Adapters, personas, contracts | ✅ |
| 06 | `plan/PHASE-06-memory-lessons.md` | Lessons, reflections | ✅ |
| 07 | `plan/PHASE-07-adg-context.md` | ADG, context pruning | ✅ |
| 08 | `plan/PHASE-08-backtrack-security.md` | Backtrack, security, ACP | ✅ |
| 08.5 | `plan/PHASE-08.5-async-cocoindex.md` | Async migration, CocoIndex, Event Store | ✅ |
| 09 | `plan/PHASE-09-health-global-skills.md` | Health, global memory, skills | ✅ |
| 10 | `plan/PHASE-10-daemon-dreamer-lazy-context.md` | Daemon, Dreamer, lazy context | ✅ |
| 11 | `plan/PHASE-11-channels-openclaw-extensions.md` | Channels, OpenClaw, plugins | ✅ |
| 12 | `plan/PHASE-12-integration-perf-testing.md` | Integration tests, perf baseline, NFR validation | ✅ |
| **13** | **`plan/PHASE-13-docs-release-engineering.md`** | **User docs, packaging, release automation** | **🔲 not-started (Fork B)** |
| A1 | `plan/fork-a/PHASE-A1-commitgate-extract.md` | Carve Proposal/Validator/Executor + Event Store as `commitgate` library | 🔲 conditional (Fork A only) |

### Status Legend

- ✅ = complete
- 🔄 = in-progress
- ⚠️ = scaffolded, backend pending
- 🔲 = not-started

---

## 3. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        CLI (typer)                           │
│  forge init | status | stage | gate | agent | lesson | ...   │
└──────────────────────────┬───────────────────────────────────┘
                           │ delegates to
┌──────────────────────────▼───────────────────────────────────┐
│                     Use Cases Layer                          │
│  BacktrackUseCases | SecurityUseCases | GateUseCases | ACP   │
└──────────────────────────┬───────────────────────────────────┘
                           │ orchestrates
┌──────────────────────────▼───────────────────────────────────┐
│                      Core Engine                             │
│  StateManager | EventBus | GateCoordinator | ContextPruner   │
└──────┬──────────────────────┬───────────────────┬────────────┘
       │                      │                   │
┌──────▼──────┐    ┌─────────▼─────────┐  ┌──────▼──────────┐
│  Adapters   │    │  Memory System    │  │  ACP Layer       │
│  KernelAdpt │    │  Lessons/LKG      │  │  ACPClient       │
│  DummyAdpt  │    │  Reflections      │  │  RegistryAdptr   │
│  LLM ...    │    │  Global Memory    │  │  Session Mgmt    │
└─────────────┘    └───────────────────┘  └─────────────────┘
```

## 4. Source Tree (Key Modules)

```
src/forge_os/
├── adapters/          # KernelAdapter protocol + implementations (sync + async from 08.5)
├── agents/            # Personas, output contracts, executor (async from 08.5)
├── cli/
│   ├── main.py        # Root app (895 lines)
│   └── commands/      # Phase 08+ command modules (backtrack, security, acp, health)
├── config/            # Config loading and validation
├── context/           # Artifact registry, ADG, context pruner (CocoIndex-backed from 08.5)
├── core/              # StateManager, atomic writes, stage transitions
├── events/            # Event bus, event log, event model (Event Store evolving from 08.5)
├── gates/             # Gate coordinator, evaluator, loader (ext/missing gates in 08)
├── hooks/             # Hook registry
├── kernel/            # Phase 08: ACPClient, ACPRegistryAdapter, async HTTP
├── memory/            # Lessons, reflections (Event Store integration in 08.5+)
├── project/           # Detection, scaffold, backtrack_registry, rework_planner,
│                      # security_enforcer, security_audit
├── schemas/           # Pydantic models (state, config, backtrack, security)
└── use_cases/         # Business logic (backtrack, security, gates)
```

---

## 5. Clean Code & Separation of Concerns (Non-Negotiable)

### Layer Architecture (Strict Dependency Direction)

```
CLI (cli/)  ──calls──▶  Use Cases (use_cases/)  ──calls──▶  Domain (core/, project/, gates/, ...)
    │                           │                                  │
    │ no business logic         │ sole orchestrator               │ no upward imports
    │ no domain imports         │ catches domain exceptions        │ no CLI knowledge
    │ format only               │ returns domain objects           │ Pydantic in/out
```

### Specific Rules

| Rule | Enforced At | Violation Example |
|------|------------|-------------------|
| **CLI never imports domain modules** | Code review / grep | `from forge_os.gates import GateCoordinator` in `cli/main.py` |
| **CLI never contains conditionals about domain state** | Code review | `if state.current_stage_id is None:` in a CLI command handler |
| **Use cases are the sole bridge between CLI and domain** | Phase gate | Creating a new command without a corresponding use case method |
| **Schemas have zero imports from `forge_os`** | `ruff check` | `from forge_os.core import ...` inside `schemas/` |
| **No `as any` / `Any` escape hatches** | Code review | `result: Any = ...` to bypass type checking |
| **Every module has a corresponding test file** | `pytest --co` | `src/forge_os/foo/bar.py` without `tests/test_foo_bar.py` |
| **All state mutations go through StateManager** | Grep | Direct `json.dump` to `.forge/state.json` outside `core/` |

### Code Review Gate (run before merging ANY code)

```bash
# 1. Check for upward imports (domain → CLI is forbidden)
grep -rn "forge_os\.cli" src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ src/forge_os/memory/ src/forge_os/context/ src/forge_os/kernel/ src/forge_os/events/ src/forge_os/hooks/

# 2. Check for business logic in CLI
grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/

# 3. Check for direct state.json access outside core/
grep -rn "state\.json\|forge_dir" src/forge_os/ --include="*.py" | grep -v "forge_os/core/" | grep -v "__pycache__"

# 4. Check for missing tests
for f in $(find src/forge_os -name "*.py" -not -path "*/__pycache__/*" -not -name "__init__.py" -not -name "models.py"); do
  module=$(echo $f | sed 's|src/forge_os/||; s|\.py$||; s|/|_|g')
  test_file="tests/test_${module}.py"
  if [ ! -f "$test_file" ]; then
    echo "⚠️  Missing: $test_file"
  fi
done
```

### Known Violations (Pre-existing — fix as encountered)

| Location | Violation | Fix |
|----------|-----------|-----|
| `cli/main.py:31` | `from forge_os.gates import GateCoordinator` — CLI imports domain directly | Route gate commands through `GateUseCases` instead |
| `cli/main.py:29` | `from forge_os.core import StateManager` — CLI imports domain directly | Keep only `StateError` for exception catching; delegate rest to use cases |
| `cli/commands/_shared.py:19,49` | `from forge_os.core import StateManager` — shared helper bypasses use cases | Move project resolution into `ProjectUseCases` |
| `cli/main.py:gate_check()` | Calls `GateCoordinator.evaluate_stage()` directly | Delegate to `GateUseCases.evaluate()` |
| `cli/main.py:gate_report()` | Calls `GateCoordinator.render_report()` directly | Delegate to `GateUseCases.report()` |
| `project/status.py:20` | Loads `state.json` directly (outside `core/StateManager`) | Re-export through `StateManager` public API |

### File Organization

```
New CLI command:     src/forge_os/cli/commands/<domain>.py → typer sub-app
New business logic:  src/forge_os/use_cases/<domain>.py    → use case class
New domain model:    src/forge_os/schemas/<domain>.py      → pydantic model
New infra/module:    src/forge_os/<module>/<file>.py
New tests:           tests/test_<module>.py
```

### Testing
- `pytest` is the test runner.
- Tests must not depend on network or external services (mock all HTTP).
- Phase 08 tests target: 120+ total (currently 67).
- Mock fixtures for ACP registry: `tests/fixtures/acp_registry.json`.
- Every use case has a corresponding unit test file.
- Integration tests may use the full `StateManager` but must not write to real filesystems (use `tmp_path`).

---

## 6. Key References

| Document | When to Read |
|----------|-------------|
| `BUILD_SPEC.md` | Before any implementation — compact source of truth |
| `plan/ORCHESTRATOR.md` | Phase execution rules |
| `plan/CURRENT_PHASE.md` | Current execution pointer (check first) |
| `ARCHITECTURE.md` | System architecture decisions |
| `ADR.md` | Architecture Decision Records |
| `plan/KERNEL_ADAPTER_INTERFACE.md` | When touching adapters |
| `plan/ADAPTER_ROADMAP.md` | Adapter priority order |
| `SCHEMAS.md` | Data model schemas |
| `plan/v4/KERNEL_UPDATED_PLAN.md` | ACP implementation blueprint |
| `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` | CocoIndex research |
| `plan/v4/SRSv4.1.md` | Full v4 specification |

---

## 7. Quick Start for Implementers

```bash
# Setup
pip install -e .[dev]

# Verify setup
forge --help
forge init --path ./my-project --profile minimal

# Run tests
pytest

# Run linter
ruff check src tests

# View current phase status
cat plan/CURRENT_PHASE.md

# View full phase plan
cat plan/PHASE-08-backtrack-security.md
```
