# PLAYBOOK — Execution Discipline

> Cross-cutting orchestration rules + clean architecture + clean code + separation of concerns. Applies to **every fork**, every track, every commit. Created 2026-05-13 as part of the strategic pivot recorded in `/STATUS.md`.
>
> **Read order each session:** `/STATUS.md` → this file → `plan/CURRENT_PHASE.md` → the file you're touching.
>
> Strategic state lives in `/STATUS.md`. Tactical phase state in `plan/CURRENT_PHASE.md`. Phase execution mode (Fork B) in `plan/ORCHESTRATOR.md`. Architecture decisions in `ARCHITECTURE.md`. Lessons in `tasks/lessons.md`.
>
> This file integrates them. It is not a replacement; it is the missing map.

---

## 0. The mission gate

**Every action must answer:** *"Does this connect a missing dot in the software engineering ecosystem for an identified user?"*

If you can't name the dot or the user, **stop**. Identified users live in `STATUS.md` D4. Until D4 is filled, every action is a strategic-pivot action — not a build action.

---

## 1. The execution loop

Every track follows this loop. The unit of iteration is a **slice** — smaller than a phase, larger than a commit (typically 1-3 commits delivering one observable behavior).

```
DECIDE  →  PLAN  →  SLICE  →  EXECUTE  →  VERIFY  →  COMMIT  →  REFLECT
   ↑                                                                ↓
   └────────────────────── lessons feed back ──────────────────────┘
```

### DECIDE
- `cat STATUS.md` — strategic state current?
- `cat plan/CURRENT_PHASE.md` — tactical state current?
- `git log --oneline -10 && git status && git diff HEAD` — repo state current?
- `cat plan/RESUME.md 2>/dev/null` — anything mid-flight?
- If anything is **paused** or **blocked**, do not proceed.

### PLAN
- Non-trivial work (3+ steps or architectural decisions) gets a written plan.
- Plan answers: **what changes, why, where, how to verify, what could break.**
- Plan locations:
  - Strategic decisions → `STATUS.md`
  - Phase work → `plan/PHASE-*.md`
  - Ad-hoc work → `tasks/todo.md` or in-conversation TodoWrite
  - Architectural decisions → new `adr/ADR-NNN-*.md`

### SLICE
- Cut the plan into units that each deliver **one observable behavior** in 1-3 commits.
- A slice is shippable on its own (tests pass, no broken contract).
- If a slice can't be made shippable, the design is wrong — re-slice.

### EXECUTE
- **Read before edit.** Always. Surrounding 50-100 lines too.
- Use parallel tool calls for independent reads/searches.
- Use subagents for breadth (multi-file analysis, parallel research, large-context protection).
- Don't refactor while implementing; don't implement while refactoring. **Separate commits.**
- One change at a time when debugging — multiple simultaneous changes obscure causation.

### VERIFY (the gate before COMMIT)
See per-commit checklist in §6.

### COMMIT
See commit discipline in §6.

### REFLECT
- If the user corrected anything: **lesson FIRST**, fix second, lesson ID in commit message third.
- If a verification step failed unexpectedly: capture *why* in the lesson body.
- If a slice took >2× estimate: note it; re-examine the slicing strategy.

---

## 2. Clean Architecture — the canonical layers

Source of truth: `ARCHITECTURE.md` "Clean Code & Layer Separation" + `CLAUDE.md` "Strict Layer Architecture." This playbook adds: **the layer rules apply to every fork, not just forge-os.**

### Forge OS (Fork B)
```
cli/   →   use_cases/   →   { core, project, gates, memory, context, kernel, events, hooks, agents, adapters }   →   schemas/
```

### CommitGate (Fork A)
```
cli/   →   boundary/   →   { validators/, store/, adapters/ }   →   core/  (Proposal, Validator protocol, Result, Executor)
```

### Universal rules (apply to both forks and any future code)

1. **Imports flow downward only.** Domain never imports from CLI. Use cases are the bridge.
2. **Schemas/types layer has zero in-package imports.** Pure data. Importable by all upper layers.
3. **No `Any` escape hatches** to bypass type checking. If you need one, write down why in a comment.
4. **Every implementation module has a corresponding test file.** `src/x/y.py` ⇒ `tests/test_x_y.py`.
5. **All state mutations through one component.** `StateManager` in forge-os; `Boundary` in commitgate.
6. **Every component replaceable through an interface.** Protocols/ABCs at the boundary; concrete types behind.
7. **Schemas are the only types crossing layers.** Never pass framework objects (Typer, Click, Rich) into the domain.

---

## 3. Clean Code — the rules linters don't catch

Linters (ruff E/F/I/UP/B) catch syntax, imports, formatting, and obvious bugs. These ten are the rules a human reviewer applies:

1. **Read before edit.** Always. Surrounding 50-100 lines too. (Yes, this is rule §1.EXECUTE too — that's how important it is.)
2. **Match existing style.** Naming, formatting, structure, idioms. Consistency in a module beats personal preference.
3. **Names describe intent, not type.** `users` not `userArray`. `is_ready` not `flag`. `forge_dir` not `path`.
4. **Functions do one thing.** If you need "and" to describe it, split it.
5. **Early returns over nested conditionals.** Reduce indentation, separate guards from logic.
6. **≤4 args per function.** Group related args into a Pydantic model or dataclass.
7. **Comments explain WHY, not WHAT.** The code shows what. Document non-obvious invariants, gotchas, decisions.
8. **No dead code, no commented-out blocks, no `TODO` without owner+ticket.**
9. **Errors are specific, contextual, loud.** Catch named exceptions, not bare `Exception`. Include input + what failed.
10. **Stale comments are worse than no comments.** Update comments when changing code, or delete them.

---

## 4. Separation of Concerns — enforced by grep

Run these four greps before every commit. **Zero matches required.** They are the executable form of the layer architecture.

```bash
# G1. Domain → CLI upward imports (forbidden)
grep -rn "forge_os\.cli" \
  src/forge_os/core/ src/forge_os/project/ src/forge_os/gates/ \
  src/forge_os/memory/ src/forge_os/context/ src/forge_os/kernel/ \
  src/forge_os/events/ src/forge_os/hooks/

# G2. CLI → domain direct imports (only StateError allowed; new code must use use_cases)
grep -rn "from forge_os\.\(gates\|core\|context\|memory\|project\) import" src/forge_os/cli/

# G3. Direct state.json access outside core/ (forbidden — only StateManager writes)
grep -rn "state\.json\|forge_dir" src/forge_os/ --include="*.py" \
  | grep -v "forge_os/core/" | grep -v "__pycache__"

# G4. Schema layer purity — only stdlib/pydantic imports allowed
grep -rn "from forge_os" src/forge_os/schemas/ --include="*.py"
```

For commitgate (when Fork A is live), the equivalent greps target `commitgate.cli`, `commitgate.core`, `commitgate.store`, `commitgate.validators`.

**Pre-existing violations** are listed in `AGENTS.md` §5. **Do not extend them; do fix them when you touch surrounding code.**

---

## 5. Decision tree — "where does this go?"

```
Is it a typed data shape with no logic?
  → schemas/<domain>.py  (Pydantic, no in-package imports)

Is it the WHEN/WHETHER decision of a domain operation?  (orchestration)
  → use_cases/<domain>.py

Is it the HOW of a domain operation?  (mechanism)
  → <domain>/<file>.py   (core/, gates/, memory/, kernel/, etc.)

Is it argument parsing or output formatting?
  → cli/commands/<domain>.py  (Typer sub-app, calls use_cases only)

Is it a contract / interface between components?
  → schemas/ (data contracts) or <domain>/base.py (protocol/ABC)

Is it shared infrastructure (atomic write, hashing, paths)?
  → core/_shared/ or a dedicated infra module — never inside cli/

Is it test-only utility?
  → tests/conftest.py or tests/_helpers/
```

If the answer is "two of these" — re-read your design. The split is wrong.

---

## 6. Per-commit checklist (copy-paste before every commit)

```
[ ] Read every file I edited (Edit fails without prior Read for a reason)
[ ] Plan exists for non-trivial work (TodoWrite or tasks/todo.md)
[ ] Tests pass:           .venv/bin/python -m pytest
[ ] Lint clean:           .venv/bin/python -m ruff check src tests
[ ] Compileall clean:     .venv/bin/python -m compileall src tests
[ ] Layer-rule grep §4 — all four return zero matches
[ ] No new pre-existing-violation extensions (AGENTS.md §5)
[ ] Manual smoke test of the user-facing path I changed
[ ] No debug prints, no commented-out code, no stale comments
[ ] Commit message: imperative subject, references task/lesson ID
[ ] Stage explicitly (no git add -A); review the diff before committing
[ ] If the user corrected me earlier: lesson written FIRST, fix second
[ ] No destructive op (push --force, reset --hard, branch -D) without explicit approval
```

**Commit message format:**
```
<type>: <imperative subject ≤72 chars>

<why this change exists; what's surprising; non-obvious context>

<task ID if applicable: P10.04>
<lesson ID if applicable: Lesson: L004>
```

`<type>` ∈ `feat | fix | refactor | test | docs | chore | perf`.

---

## 7. Per-feature checklist (one feature = N slices)

```
[ ] Decision recorded (plan/PHASE-*.md, STATUS.md, or new ADR)
[ ] Use case method exists in use_cases/<domain>.py
[ ] Domain code in <domain>/<file>.py (or new module)
[ ] Schemas in schemas/<domain>.py (no upward imports)
[ ] CLI sub-app in cli/commands/<domain>.py (Typer; calls use_case only)
[ ] Sub-app registered in cli/main.py via app.add_typer()
[ ] Tests for use case (tests/test_use_cases_<domain>.py)
[ ] Tests for domain code (tests/test_<domain>_<file>.py)
[ ] No network in tests; tmp_path for state (Lesson L001)
[ ] User-facing behavior demonstrated end-to-end (not just "tests pass")
[ ] CHANGELOG entry or STATUS.md change-log line if user-visible
```

---

## 8. Per-track checklist (one track = N features)

A track is a sustained line of work — a phase, a release, a Fork. Before starting, before each weekly review, and at exit:

```
[ ] Strategic state confirms this track is active (STATUS.md D5 resolved)
[ ] Tactical state pointer updated (CURRENT_PHASE.md or STATUS.md)
[ ] Kill criterion set (numeric, dated) BEFORE any code is written
[ ] Owner is one named human
[ ] Review cadence set (weekly default; biweekly minimum)
[ ] All deliverables traceable to a slice
[ ] Exit criteria written before starting (not retrofitted)
[ ] Tests added for every slice
[ ] CHANGELOG (if shipping) or summary in STATUS.md change log
[ ] At exit: lessons captured for what surprised you
```

---

## 9. Subagent dispatch policy

**Use subagents when:**
- Open-ended search across many files (`Explore` for narrow lookup; `general-purpose` for breadth).
- Independent parallel work (e.g. four reviewers each on a different slice).
- Protecting the main context from large reads (research reports, full SRS scans).
- A specialized agent type fits (e.g. `oh-my-claudecode:critic` for skeptical review).

**Do NOT use subagents when:**
- The target is known — use `Read` or `grep` directly. (`Read foo.py:120-180` beats spawning Explore.)
- Implementation needs full session context — keep it in the main thread.
- The user is in a back-and-forth design dialog — context-switching loses thread.

**One task per subagent.** Pass narrow, explicit prompts. Always ask: *can this be parallelized?* When dispatching multiple agents for independent work, send them in **one message** with multiple tool blocks so they run concurrently.

---

## 10. Interruption protocol

If a session may be interrupted or context reset:

1. Write `plan/RESUME.md` with: current track, completed slices, pending slice (next action), decisions made not yet in code/docs, expected failing tests, files mid-edit.
2. Save it **before any other action.**
3. The resume prompt must be a valid instruction a fresh agent can follow without reading this conversation.

On session start, the order is: `STATUS.md` → `PLAYBOOK.md` (this) → `CURRENT_PHASE.md` → `RESUME.md` (if exists) → the file you're touching.

---

## 11. Anti-patterns (refuse these)

- ❌ Editing files you haven't read
- ❌ "Fix" by deleting the failing test
- ❌ `try: ... except: pass` to silence errors
- ❌ Mock-only tests that don't exercise real behavior
- ❌ Copy-paste over extracting a function (when duplication is real, not coincidental)
- ❌ Adding flags/options to avoid making a decision
- ❌ Premature abstraction (one caller, three layers of indirection)
- ❌ Comments that lie ("returns user" when it returns null half the time)
- ❌ Disabling lint rules instead of fixing the issue
- ❌ Reformatting unrelated code in the same diff as a behavior change
- ❌ Adding scope without an ADR
- ❌ Continuing tactical work while strategic state is paused
- ❌ Ignoring `tasks/lessons.md` entries
- ❌ Marking a task complete without proving it works
- ❌ "It works on my machine" without checking the actual deployment context

---

## 12. How this playbook applies per fork

| Fork | How the playbook scopes |
|---|---|
| **A — commitgate** | Layer rules apply with the commitgate mapping (§2). Surface is smaller, so checklists are shorter, but **kill criterion (D8) and adapter choice (D6) gate every commit.** Do not start Week 1 until D8 is filled in. |
| **B — continue forge-os scoped to v2** | Phase-based execution per `plan/ORCHESTRATOR.md` continues (it's the operating-mode handbook). **v4 scope strictly out** — every phase entry must verify it's in `SRSv2.md` scope, not v4.1. PHASE-08.5's CocoIndex workstream stays marked complete (mtime cache landed) but no further CocoIndex work. |
| **C — research** | All rules become **guidance, not enforcement**. Verification can be informal. Keep the lesson loop active because future-you is the user. README must say `STATUS: research project, not a product` so external readers don't misinterpret. |

The playbook itself doesn't change between forks — only which checklists are tightly enforced.

---

## 13. Index of canonical documents

| File | Scope | When to read |
|---|---|---|
| `STATUS.md` | Strategic state — fork decision, kill criteria, mission | First, every session |
| `plan/PLAYBOOK.md` | This file — orchestration + arch + code + SoC | Second, every session |
| `plan/CURRENT_PHASE.md` | Tactical phase state | When doing phase work |
| `plan/ORCHESTRATOR.md` | Phase execution rules (Fork B operating mode) | When running phases |
| `plan/RESUME.md` | Mid-flight recovery | When resuming an interrupted session |
| `AGENTS.md` | Project orchestration guide; pre-existing violations table | When uncertain about discipline rules |
| `CLAUDE.md` | Claude Code-specific entry; layer rules concretized; lessons summary | When starting work in Claude Code |
| `ARCHITECTURE.md` | Architecture decisions; layer diagram | When designing a new module |
| `BUILD_SPEC.md` | Product invariants; canonical project layout | When questioning fundamentals |
| `SCHEMAS.md` | Data contracts; format decisions | When defining a new schema |
| `tasks/lessons.md` | Captured lessons (L001-L005) | Every time the user corrects you |
| `adr/ADR-*.md` | Decisions on individual technical questions | When a similar decision recurs |

---

## 14. Change log

| Date | Change |
|---|---|
| 2026-05-13 | Created. Consolidates orchestration + clean arch + clean code + SoC into a single fork-agnostic playbook. References existing canonical sources rather than duplicating them. |
