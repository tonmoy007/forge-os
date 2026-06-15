# Contributing to Forge OS

Thanks for your interest in Forge OS. This guide covers how to set up a dev
environment, the quality bar every change must clear, and how pull requests are
made and merged.

Forge OS is local-first and kernel-agnostic: the orchestration engine owns
canonical state, and AI providers, humans, and plugins are execution surfaces
only. Keep that boundary in mind when proposing changes.

For the deeper rationale behind these rules, see [`AGENTS.md`](AGENTS.md),
[`ARCHITECTURE.md`](ARCHITECTURE.md), [`CLAUDE.md`](CLAUDE.md), and the focused
rule files under [`.claude/rules/`](.claude/rules/).

---

## Code of conduct

Be respectful, assume good faith, and keep discussion technical. Harassment or
personal attacks are not tolerated. Report concerns to the maintainer via a
private channel (see the repository owner's profile).

---

## Getting started

Requires Python 3.11+.

```bash
git clone https://github.com/tonmoy007/forge-os && cd forge-os
pip install -e '.[dev]'

forge --version          # sanity check the entrypoint
python -m pytest -q      # baseline suite should be all green
```

The reference environment is a clean `python:3.12-slim` container. CI
(`.github/workflows/ci.yml`) runs the full gate against **Python 3.11 and 3.12**
on every pull request — match that locally before you push.

---

## Architecture rules (do not break these)

Forge OS enforces a strict, one-directional layering:

```
cli/  ──▶  use_cases/  ──▶  core/, gates/, project/, context/, memory/,
                            kernel/, events/, hooks/, agents/, adapters/
                                            │
                                            ▼
                                       schemas/   (pure Pydantic, zero internal imports)
```

- `cli/` parses args, calls exactly one `use_cases/` method, renders output. It
  must not import domain modules directly (except `StateError`).
- Domain modules never import upward from `cli/` or `use_cases/`.
- `schemas/` is pure Pydantic with zero imports from other `forge_os` modules.
- `StateManager` is the **only** writer of `.forge/state.json`.
- The engine never imports a provider SDK — kernels plug in through the
  `KernelAdapter` boundary only.

New CLI command? Domain logic → a domain module; a use-case method in
`use_cases/`; a thin Typer sub-app in `cli/commands/` registered in `main.py`.

---

## Tests are required

- No new feature without tests; no bug fix without a regression test that fails
  before your fix and passes after.
- Every module `src/forge_os/foo/bar.py` has a matching `tests/test_foo_bar.py`.
- Tests must be deterministic and isolated — no real network, no shared mutable
  state, no `sleep`. Modules that persist under `~/.forge/` must accept a
  `forge_dir: Path | None = None` parameter so tests can pass `tmp_path`.
- Test behavior, not implementation. Cover the happy path, edge cases, and error
  paths.

---

## Before you open a pull request

Run the same gate CI runs, from the repo root:

```bash
python -m ruff check src tests     # lint — must be clean (rules E F I UP B, line length 100)
python -m pytest -q                # full suite — must be all green
python -m compileall -q src tests  # syntax sweep
```

A PR that does not pass these locally will not pass CI.

---

## Commit style

- One logical change per commit. Don't bundle "fix bug" + "add feature" +
  "refactor" — split them.
- Imperative mood, summary under ~72 chars:
  `feat: add OpenCode adapter retry backoff`, not `Added retries`.
- Use a Conventional Commit prefix: `feat`, `fix`, `docs`, `test`, `refactor`,
  `chore`, `build`, `ci`.
- The body explains **why**; the diff shows **what**. Reference the phase/task or
  SRS requirement ID where one applies (e.g. `(P10.11)`, `FR-KA-001`).
- Refactors and behavior changes go in **separate** commits.
- Never commit secrets, `.env` files, generated artifacts, or build output.

---

## Pull requests

1. **Branch from `main`.** `main` is protected — all changes land via PR, never a
   direct push. Name branches by intent: `feat/…`, `fix/…`, `docs/…`,
   `chore/…`, `ci/…`, `build/…`.
2. **Keep PRs reviewable** — aim for under ~400 lines of diff. Split larger work
   into sequential PRs that each stand on their own.
3. **Write a useful description:** what changed, why, how to test, and any risk
   or trade-off. Link related issues.
4. **CI must be green** — the `validate (3.11)` and `validate (3.12)` checks are
   required and must pass before a PR is mergeable.
5. **Keep your branch up to date** with `main` before merge.
6. **The maintainer reviews and merges.** Only the repository owner merges to
   `main`. Don't merge your own PR unless you are the maintainer.
7. After merge, delete the branch.

Opening a PR with the GitHub CLI:

```bash
git switch -c feat/my-change
# … commits …
git push -u origin feat/my-change
gh pr create --base main --fill
```

---

## Reporting bugs and security issues

- **Bugs / features:** open a GitHub issue with steps to reproduce, expected vs
  actual behavior, and your environment (OS, Python version, adapter).
- **Security:** do **not** open a public issue for a vulnerability. See
  [`SECURITY_BASELINE.md`](SECURITY_BASELINE.md) and contact the maintainer
  privately so the issue can be fixed before disclosure.

---

## License

By contributing, you agree that your contributions are licensed under the
project's [Apache-2.0](LICENSE) license.
