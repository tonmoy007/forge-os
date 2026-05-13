# PHASE-13 — Documentation & Release Engineering

> **Scope-conditional:** applies under **Fork B** (continue forge-os scoped to v2).
>
> **Prerequisites:** Phase 12 complete (you ship from a measured baseline, not vibes).
>
> **PLAYBOOK:** §6 per-commit checklist; §7 per-feature checklist.

---

## 1. Objective

Take forge-os from "feature-complete dev tool that works on the author's machine" to "installable, documented, ship-able to an external user." Phases 01-11 build features. No phase before this owns the path to a release. Without this phase, the project never reaches D4's "named users."

## 2. ADR alignment

| ADR | How this phase honors it |
|---|---|
| ADR-001 (Python 3.11+, `uv`/`pip`, `pipx`) | Validates `pip` and `pipx` install paths on Linux, macOS, Windows. Standalone binary remains deferred per ADR-001. |
| ADR-002 (local-first) | Quickstart works without network beyond the initial `pip install`. |
| ADR-003 (open formats) | All user-facing docs in Markdown; CHANGELOG plain text; release artifacts in standard wheel/sdist. |

## 3. Scope

**In:**
- Quickstart guide: `pip install forge-os` to first completed minimal-profile cycle in <30 minutes (NF-U-01 from SRS).
- Reference docs: every CLI command, every config field, every event type, every lesson lifecycle state.
- Concept docs aimed at *external* readers (vs the internal-only ADRs/ARCHITECTURE.md).
- Packaging validation: `pip install forge-os` and `pipx install forge-os` both work on macOS, Linux, Windows.
- Release automation: CHANGELOG generated from commit history; semver bumping via `pyproject.toml`.
- Public README rewrite (currently has stale Phase-08.5/CocoIndex references — STATUS.md D1).
- D1 cleanup: purge CocoIndex from all user-facing docs (lesson L004 already locked the technical decision; this phase finishes the doc hygiene).

**Out (deferred or v4 scope):**
- Standalone binary distribution (deferred per ADR-001).
- Multi-language documentation (v2 is English-only).
- Web/IDE plugin docs (Phase 11+ scope).
- Hosted documentation site (markdown-in-repo is sufficient for v2).

## 4. Dependencies

- Phase 11 complete (or 11-partial if shipping pre-OpenClawAdapter; document the limitation explicitly).
- D1 CocoIndex doc cleanup wrapped into this phase as P13.01.

## 5. Deliverables

| Item | Path |
|---|---|
| Quickstart guide | `docs/quickstart.md` |
| CLI reference (auto-generated where possible) | `docs/cli-reference.md` |
| Config reference (extracted from Pydantic schemas) | `docs/config.md` |
| Concepts guide (stages, gates, lessons, ADG, adapters) | `docs/concepts.md` |
| Profile guide (minimal / standard / expert) | `docs/profiles.md` |
| Release process doc | `docs/RELEASING.md` |
| CHANGELOG | `CHANGELOG.md` (project root) |
| Updated README | `README.md` (replaces Phase 08.5 status block; current install instructions) |
| GitHub Actions release workflow | `.github/workflows/release.yml` |
| pyproject.toml metadata audit | `pyproject.toml` (classifiers, license file, keywords, description) |
| First release candidate | TestPyPI 0.5.0-rc1 |

## 6. Tasks

| ID | Task | Effort | Notes |
|---|---|---|---|
| P13.01 | D1 cleanup: remove CocoIndex references from `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`, `IMPLEMENTATION_PLAN.md`, `plan/ORCHESTRATOR.md`, `ADR.md` (delete the line that references nonexistent ADR-010), and consider parking `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` | M | One commit per file group |
| P13.02 | Quickstart guide | M | Test by walking a non-author through it |
| P13.03 | CLI reference (script extracts Typer help → markdown) | M | Auto-regenerate in CI |
| P13.04 | Config reference (extract from Pydantic schemas) | S | Auto-regenerate in CI |
| P13.05 | Concepts guide | L | Stages, gates, lessons, ADG, adapters, the lesson lifecycle |
| P13.06 | Profile guide | S | When to pick minimal vs standard vs expert; how to migrate up |
| P13.07 | README rewrite | M | Status, install, quickstart link, working/upcoming, link to STATUS.md and PLAYBOOK.md |
| P13.08 | Verify clean `pip install -e .[dev]` from a fresh venv on Linux | S | |
| P13.09 | TestPyPI publish dry-run; verify `pipx install --index-url ... forge-os` | S | |
| P13.10 | macOS + Windows install smoke tests in CI matrix | M | |
| P13.11 | CHANGELOG generator script + first `CHANGELOG.md` | S | Conventional commits → release notes |
| P13.12 | Release process doc | S | Semver, branch policy, tag conventions, who publishes |
| P13.13 | GitHub Actions release workflow | M | Trigger on tag; publish wheel + sdist to PyPI; create GitHub release with CHANGELOG slice |
| P13.14 | pyproject.toml metadata audit | S | Classifiers (Topic, License, Python versions); long_description from README |
| P13.15 | First release candidate to TestPyPI: 0.5.0-rc1 | S | |

## 7. Acceptance criteria

- [ ] A new developer can go from `pip install forge-os` to `forge stage advance` in <30 minutes by following only the quickstart (validated with at least one non-author tester from STATUS.md D4).
- [ ] All CLI commands documented; `forge <cmd> --help` matches `docs/cli-reference.md`.
- [ ] No "Phase 08.5", "CocoIndex", or "evaluating" references in `README.md` or any other user-facing doc.
- [ ] `pipx install forge-os` works on at least Linux + macOS (Windows tested in CI but may be best-effort).
- [ ] `CHANGELOG.md` exists; covers all releases from 0.1.
- [ ] Release workflow successfully publishes 0.5.0-rc1 to TestPyPI.
- [ ] `pyproject.toml` includes accurate classifiers, license-file pointer, and long_description.

## 8. Exit checklist

- [ ] All P13.xx tasks complete.
- [ ] `pipx install forge-os` succeeds in a fresh container.
- [ ] First release candidate published to TestPyPI; install validated.
- [ ] At least one D4 tester ran the quickstart and reported back (success or specific friction).
- [ ] PLAYBOOK §6 commit checklist applied per commit.
- [ ] `plan/CURRENT_PHASE.md` updated; phase marked complete; v0.5.0 release tagged.

## 9. Kill criterion (set before P13.01)

```
Track:    PHASE-13 docs & release
Kill date: <P12 complete + 60 days>
Kill if any of:
  - Quickstart can't be completed in <30 min by a non-author tester
  - PyPI metadata blocks publication (license, name conflict)
  - Zero D4 testers willing to install rc1 (means D4 itself was never honest)
  - More than 7 days spent on the README rewrite (rewrite scope-creep)
Owner:           <single named human>
Review cadence:  weekly
```

## 10. Suggested next prompt

After P12 exit and Phase 13 prereqs met:

> `Read plan/PHASE-13-docs-release-engineering.md and execute P13.01 (CocoIndex doc cleanup). One commit per file group. After P13.01, write the quickstart (P13.02) and have it tested by the D4 user.`
