# Forge OS — Captured Lessons

> **Purpose:** Every time the user corrects a mistake, the lesson is recorded here BEFORE fixing the code.
> The lesson is more valuable than the fix because it prevents future repetitions.

## How to Use

1. User gives a correction.
2. **First:** Add an entry to this file with date, trigger, root cause, and rule.
3. **Second:** Fix the code.
4. **Third:** Reference the lesson ID in the commit message.

## Lessons

### L001 — Global state in ~/.forge/ breaks test isolation
- **Date:** 2026-05-12
- **Trigger:** Tests failing because `GlobalLessonStore`, `ProjectProfileStore`, and `SkillUseCases` wrote to real `~/.forge/` directory, causing cross-test pollution and leftover state from prior runs.
- **Root cause:** Used `Path.home()` as default path without injection mechanism. Tests shared mutable global state.
- **Rule:** All modules that persist to `~/.forge/` MUST accept an optional `forge_dir: Path | None = None` parameter. When `None`, default to `Path.home() / ".forge"`. Tests MUST pass `tmp_path`-based directories.
- **Files affected:** `memory/global_store.py`, `memory/project_profiles.py`, `use_cases/skills.py`, `tests/test_health_phase09.py`

### L002 — Ruff `E741` blocks single-letter variable names in comprehensions
- **Date:** 2026-05-12
- **Trigger:** `ruff check` failing with `E741 ambiguous variable name: 'l'` on list comprehensions using `for l in ...`.
- **Root cause:** The `l` variable name is visually ambiguous with `1`. Ruff's `E741` rule rejects it even in throwaway comprehension variables.
- **Rule:** Use `le` (for lesson elements), `a` (for artifacts), or other unambiguous short names in comprehensions. Never use `l`, `O`, or `I` as variable names.

### L003 — SQLite WAL mode + synchronous=NORMAL is ideal for local-first CLI tools
- **Date:** 2026-05-12
- **Trigger:** Designing the Event Store for Forge OS required choosing SQLite settings that balance durability with performance for a developer-local tool.
- **Root cause:** Default SQLite settings favor maximum durability (full fsync on every write) at the cost of throughput. For a local dev tool, the last few ms of durability can be traded for performance.
- **Rule:** For local-first CLI tools using SQLite, always enable `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. WAL allows concurrent reads during writes. NORMAL trades the last few ms of fsync for throughput — acceptable for non-critical local data.

### L004 — CocoIndex requires PostgreSQL, making it unsuitable for local-first tools
- **Date:** 2026-05-12
- **Trigger:** Evaluating CocoIndex as incremental indexing engine for Context Pruner.
- **Root cause:** CocoIndex requires PostgreSQL for its metadata store. This is a hard dependency that conflicts with Forge OS's "local-first, zero-infrastructure" design principle.
- **Rule:** Before adopting any external dependency for a local-first CLI tool, verify it doesn't require a database server, network service, or cloud API. CocoIndex is suitable for server-side deployments only. For local incremental processing, use `st_mtime` caching instead.

### L005 — Inject `forge_dir` rather than hardcoding `Path.home()` in global modules
- **Date:** 2026-05-12
- **Trigger:** Multiple iterations needed to fix test isolation (a corollary to L001 with broader scope).
- **Root cause:** Several modules (`GlobalLessonStore`, `ProjectProfileStore`, `SkillUseCases`) referenced `Path.home() / ".forge"` directly, making them impossible to unit test in isolation.
- **Rule:** Any module that reads/writes to `~/.forge/` MUST accept the forge directory as a constructor parameter. The `Path.home()` default is acceptable only as a fallback when no explicit path is given. This enables both production use (no arg = ~/.forge) and test isolation (tmp_path injected).
