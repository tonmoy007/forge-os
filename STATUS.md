# STATUS — Forge OS Strategic Pivot

**Last updated:** 2026-05-13
**Author:** strategic review session (synthesis from SRS v1, v2, v4.1, current implementation, market analysis)
**Replaces (for strategic-state purposes):** `plan/CURRENT_PHASE.md` continues to track tactical phase work; this file holds strategic state.

---

## Mission (restated by the project owner, 2026-05-13)

> **Help everyone manage software engineering by connecting all the missing dots in the ecosystem.**

This is closer in spirit to the v1 SRS framing ("any developer or team to build, maintain, and evolve software with minimal manual process overhead") than to the v4.1 enterprise scope. The v1 mission is achievable; the v4.1 enterprise scope is not, at current capacity.

---

## Where we started → where we are

| Spec | Date | Scope | Estimated effort | Outcome |
|---|---|---|---|---|
| **SRS v1** (`SRS.md`) | 2026-05-06 | 12-stage SDLC, 16 agents, 3-tier memory, health daemon. Single-team focus. | ~14 months, ~1 dedicated team | The achievable original. Five of its six phases are done. |
| **SRS v2** (`SRSv2.md`) | (undated) | v1 + Background Daemon, Dreamer, Lazy Context Builder, Channel Adapter, OpenClawAdapter, sandbox, extension ecosystem. | 18-24 months, 1 team | Adds the "always-on" layer. Most of it is in scope for Phases 10-11. |
| **SRS v4.1** (`plan/v4/SRSv4.1.md`) | 2026-05-10 | v2 + Proposal/Validator/Executor boundary, OPA, gVisor, event sourcing, multi-model router, multi-tenancy, shadow evaluation, semantic tracing, Sigstore, HSM, Redpanda partitioning, OpenSpec, Microsoft AGT (parked). | 27 months × ~16 engineer team = **~177 engineer-months** | Scope sprawl. Single-developer execution makes this a >10-year solo march. |
| **Implementation today** | 2026-05-13 | Phases 00-09 complete, Phase 10 in progress. 230 tests passing, ruff clean, layer architecture enforced. | ~6 calendar days of clustered commits in May 2026 | Engineering quality is high; strategic position is unclear. |

The drift trajectory is clear: each rev added scope without subtracting. v4.1 conflated three different products (a personal SDLC CLI, an enterprise governance platform, an agent orchestration substrate) into one spec.

---

## Decisions resolved (2026-05-13)

### D1 — CocoIndex contradiction reconciled ✅

Was: `BUILD_SPEC.md:35` and `IMPORTANT_UPDATE.md:17` listed CocoIndex as recommended/BUY. `tasks/lessons.md` L004 had already rejected it (PostgreSQL dependency, incompatible with local-first / ADR-002).

Done:
- `BUILD_SPEC.md:35` and `BUILD_SPEC.md:85` now reflect rejection and point to L004.
- `plan/v4/parking-lot/IMPORTANT_UPDATE.md:17` corrected from BUY → REJECTED.
- A "PARKED" header added to the same file.

Cleanup still pending (deferred until D5/D6/D7 below resolve, to avoid editing files that may be archived):
- `ARCHITECTURE.md:26-27, 80, 171`
- `ROADMAP.md:89, 96, 97, 113`
- `AGENTS.md:73, 123, 228`
- `README.md:14-15, 86, 88, 93, 179, 195`
- `IMPLEMENTATION_PLAN.md:28`
- `ADR.md:20` references a non-existent `adr/ADR-010-cocoindex-backbone.md`
- `plan/PHASE-08.5-async-cocoindex.md` — entire workstream B; currently marked complete because the *replacement* (mtime cache) was delivered, but the title and sections still imply CocoIndex was the path
- `plan/CURRENT_PHASE.md:134, 139` references
- `plan/ORCHESTRATOR.md:10, 146`
- `plan/v4/MEMORY_CONTEXT_UPDATED_PLAN.md` — the entire 233-line CocoIndex research file; recommend parking it next to `IMPORTANT_UPDATE.md` once D5 resolves

### D2 — v4 SRS frozen ✅

Done:
- `plan/v4/parking-lot/` directory created.
- `IMPORTANT_UPDATE.md` and `SRSv4.1ADDON.md` moved into it with a parking-policy README.
- v4.1 spec proper (`SRSv4.1.md`, `KERNEL_UPDATED_PLAN.md`, `MEMORY_CONTEXT_UPDATED_PLAN.md`) remains in `plan/v4/` for reference but is **read-only** until the fork decision (D5) resolves.

Rule going forward: **no new files added to `plan/v4/` until D5 resolves.**

### D3 — Kill criteria framework defined (values pending owner input)

The principle is locked: every active build track must have a numeric, dated kill criterion before it starts. **Owner action required to fill values** for whichever tracks survive D5/D6/D7. Template:

```
Track:               <name>
Kill date:           <YYYY-MM-DD>  (typically start + 30 or 90 days)
Kill if any of:
  - <metric A> < <threshold>
  - <metric B> < <threshold>
  - <qualitative trigger, e.g. "no design partner identified">
Owner:               <single human>
Review cadence:      <weekly / biweekly>
```

---

## Decisions OPEN — owner action required

These are blockers for resuming any build work. Until they resolve, treat the codebase as in **strategic pause**.

### D4 — Name three real humans who would adopt this

> "If you can't, that's the answer."

Capture below (names, not roles). If you cannot fill three within 7 days, the answer is one of: archive (Fork B), or pivot to a primitive that has a clearer adopter (Fork A).

```
1. ___________________________  (relationship, why they'd adopt, what they'd use it for)
2. ___________________________
3. ___________________________
```

### D5 — Strategic fork ✅ RESOLVED 2026-05-13 → **B (open-source, kernel-first)**

**Decision:** Continue forge-os, scope-cut to v2, **publish as open-source** so contributors join the mission ("connect missing dots in the software-engineering ecosystem"). D4 is deferred from "3 named adopters" to "3 named contributors after launch" — the open-source path treats community-bootstrapping as the user-discovery mechanism.

**Sequencing override from original B description:** kernel adapters come **before** Phase 10 completion. Original B said "Phase 10 → 11 → 0.5 release"; revised B sequence is:

1. **Day 0:** D9 ruff baseline cleanup (single chore commit).
2. **Phase 05.5** — `ClaudeCodeAdapter` (the second priority adapter; Phase 05 is "complete" but only Dummy exists). New phase file: `plan/PHASE-05.5-claude-code-adapter.md`.
3. License flip + README rewrite (open-source readiness — Step 1-2 of the open-source plan).
4. Phase 10 finish (daemon, dreamer, lazy context).
5. Phase 11 channel adapters.
6. Phase 12 + Phase 13 (integration/perf, docs/release).
7. v0.5.0 PyPI release + community outreach.

**Rationale:** A real product needs at least one real kernel. Shipping forge-os with only DummyAdapter would invite criticism ("can't actually do anything") that no amount of architecture talk would offset.

**Forks A and C remain documented** above for reference, but are not active. PHASE-A1 in `plan/fork-a/` stays as a frozen alternative.

### D6 — First adapter (only if D5 = A)

| Adapter | Why pick it | Why not |
|---|---|---|
| **Claude Code hook** (recommended first) | You use it daily; ~60 LOC shim; easy demo (deny-on-secret on `Edit`/`Write`); concrete user is yourself. | Smaller TAM than LangGraph; tied to Anthropic. |
| **LangGraph node wrapper** | Largest TAM in agent orchestration; demonstrates composition with the dominant framework. | More integration surface; you're not a LangGraph user; less honest dogfood. |
| **Raw Python (no adapter)** | Ships fastest; minimum surface to maintain; users wire it in themselves. | Weakest demo; no obvious "look how easy this is" story. |

### D7 — Forge-os fate (only if D5 = A)

- **Consumer:** keep the 12-stage thing as private dogfood for `commitgate`. **Don't ship it.** Don't promise it externally. Stop adding features. Leave Phase 10 partly done if needed.
- **Archive:** add `STATUS.md` notice + freeze tag, redirect README to the new `commitgate` repo, stop work entirely.

### D8 — 30-day kill criterion for `commitgate` (only if D5 = A)

Numeric threshold to set **before** starting Week 1. Example shape (fill the numbers):

```
Track:    commitgate v0.1
Kill date: 2026-06-12 (start of Week 1 + 30 days)
Kill if any of:
  - GitHub stars                      < ___
  - Distinct PyPI installs (>1 week)  < ___
  - Issues filed by non-author         < ___
  - Adoption commitments by name      < 1   (set to 1: at least one named user from D4 must try it)
Owner:    <name>
Review:   day 14, day 30
```

---

## Tactical state (unchanged by this strategic pivot)

- Phase 09 complete (commit `58065ae`).
- Phase 10 in progress per `plan/CURRENT_PHASE.md`. **Pause Phase 10 work until D5 resolves.**
- 230 tests pass.
- ⚠️ **`ruff check src` reports 114 errors** (78 E501 line-too-long, 10 P045, 8 I001 import-sort, 5 B904 raise-from, 4 E402 module-import-not-at-top, 3 P042, 3 P035, 2 F401 unused-imports, 1 P015). `STATUS.md`/`CURRENT_PHASE.md` previously claimed "ruff clean" — that claim was stale. None caused by this session (no Python was edited). 24 are auto-fixable.
- compileall: clean.
- Layer architecture enforced (see `CLAUDE.md` for the grep-based checks).
- Lessons L001-L005 in force; honor `forge_dir` injection pattern, ruff E741, SQLite WAL+NORMAL, no-Postgres-dependency rule.

### D9 — Baseline cleanup before any new track starts ✅ RESOLVED 2026-05-13

**Commit:** `b5cbd50` — `chore: restore ruff-clean baseline (114 → 0) (D9)`

114 pre-existing ruff errors cleared: 77 E501 (typer.Option lines reformatted), 5 B904, 4 E402, 3 UP042 (StrEnum), misc import sorts and unused imports. 230 tests pass. All 4 PLAYBOOK grep gates clean. Ruff baseline is now a hard invariant — PLAYBOOK §6 requires `ruff check src tests` to return 0 before every commit.

## Execution discipline (applies to every fork)

How work proceeds — orchestration loop, clean architecture, clean code, separation of concerns, per-commit / per-feature / per-track checklists — is consolidated in **`plan/PLAYBOOK.md`**. The playbook is fork-agnostic; it applies whether D5 resolves to A (commitgate), B (continue forge-os), or C (research). Phase-mode specifics layered on top live in `plan/ORCHESTRATOR.md`.

---

## Why this exists

This file is the answer to a question the project did not previously have an answer to: **what should the next decision be?** Phase planning told us *how* to build but not *whether* to keep building, and the v4 SRS kept growing without anyone asking that question.

The mission you stated — *connecting missing dots in the software engineering ecosystem* — is real and worth pursuing. But "connecting dots" is a primitive (a boundary, a protocol, a contract), not a 12-stage pipeline. The v1/v2 framing came closest; v4.1 lost the thread by trying to be the entire ecosystem instead of the connector inside it.

Resolve D4 first. The other decisions become easy once it's answered honestly.

---

## Change log

| Date | Change | By |
|---|---|---|
| 2026-05-13 | File created. CocoIndex contradiction (D1) reconciled. v4 spec frozen (D2). Kill criteria framework (D3) defined. D4-D8 captured as open. | strategic review session |
| 2026-05-13 | PLAYBOOK.md created — fork-agnostic execution discipline (orchestration loop, clean architecture, clean code, separation of concerns, per-commit/per-feature/per-track checklists). Wired into AGENTS.md, ORCHESTRATOR.md as required reading. | strategic review session |
| 2026-05-13 | Ruff baseline drift discovered (114 errors in `src/` despite "ruff clean" claim). Captured as D9 cleanup. | strategic review session |
| 2026-05-13 | ADR↔Phase coverage audit complete (8/8 ADRs honored, 0 conflicts). Three phase gaps identified and drafted: PHASE-12 (integration + perf, Fork B), PHASE-13 (docs + release, Fork B), PHASE-A1 (commitgate extract, Fork A only, in `plan/fork-a/`). Phase indexes in AGENTS.md and ORCHESTRATOR.md updated. | strategic review session |
| 2026-05-13 | D5 resolved → B (open-source, kernel-first). Sequencing locked: D9 → Phase 05.5 → license flip → Phase 10 → 11 → 12 → 13 → v0.5.0. | owner |
| 2026-05-13 | D9 resolved. 114 ruff errors → 0. Commit b5cbd50. Ruff-clean baseline is now a hard invariant. | implementation session |
