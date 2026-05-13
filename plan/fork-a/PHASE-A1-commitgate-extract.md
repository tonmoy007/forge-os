# PHASE-A1 — `commitgate` Extract (Fork A)

> **Conditional execution:** only run if `STATUS.md` D5 resolves to **Fork A**. If D5 resolves to B (continue forge-os) or C (research), archive this file unchanged.
>
> **Strategic context:** carve the deterministic Proposal → Validator → Executor + Event Store + replay primitive out of forge-os into a standalone library that plugs into Claude Code / LangGraph / AutoGen / raw Python.
>
> **Mission gate (PLAYBOOK §0):** *connect missing dots in the software-engineering ecosystem.* commitgate IS that dot — the boundary primitive between AI agent intent and committed state. No comparable primitive exists in LangGraph, AutoGen, CrewAI, Anthropic SDK, or OpenAI tool-use.

---

## 0. Pre-requirements (must all be true before Week 1 starts)

- [ ] **D4** resolved: at least one named user from `STATUS.md` D4 has agreed to try the 0.1 release.
- [ ] **D6** resolved: first adapter chosen (Claude Code hook recommended).
- [ ] **D7** resolved: forge-os fate decided (consumer or archive).
- [ ] **D8** resolved: numeric 30-day kill thresholds set in §10 below.
- [ ] **D9** resolved: ruff baseline clean.

If any of these are unfilled, **stop**. The phase has no business starting.

---

## 1. Objective

Ship `commitgate` v0.1.0 on PyPI within 3 weeks of D5 resolution. One adopter-validated integration adapter. Apply D8 kill criterion at day 30 — keep going only if real adoption signal is present.

## 2. ADR alignment (commitgate inherits these)

| ADR | How commitgate honors it |
|---|---|
| ADR-001 | Python 3.11+; `pip` + `pipx` install; no Node/Postgres/external runtime. |
| ADR-002 | Library is local-first by design — no network, no daemons, no cloud. |
| ADR-003 | Event log persisted as JSON Lines (`commitgate/store/jsonl.py`) and SQLite (`store/events.py`); both open formats. |
| ADR-004 | `Boundary` is the *only* component that mutates the event store; mirrors forge-os `StateManager` discipline. |
| ADR-005 | Adapters (Claude Code, LangGraph, AutoGen, MCP) sit at the boundary — same pattern as KernelAdapter in forge-os. |
| ADR-006 | Validators are pluggable; OPA validator is opt-in (lazy import); no hard dependency. |
| ADR-007 | The boundary itself implements least-privilege: every action passes through validators that can deny. |

## 3. Package boundary

```
commitgate/
├── core/
│   ├── proposal.py       # Proposal base class (Pydantic)
│   ├── validator.py      # Validator protocol + composers
│   ├── executor.py       # Executor protocol
│   ├── boundary.py       # Boundary orchestrator (commit, record, replay)
│   └── result.py         # CommitResult, ValidationViolation
├── store/
│   ├── events.py         # EventStore — lifted from forge-os events/store.py
│   ├── model.py          # Generic Event — lifted from events/model.py (forge-specific event types stripped)
│   ├── jsonl.py          # Optional secondary writer
│   ├── atomic.py         # Atomic-write helper
│   └── replay.py         # Replay + recorded-effects
├── validators/
│   ├── schema.py         # Pydantic-model validator
│   ├── predicate.py      # Lambda/callable validator
│   ├── command.py        # External command (timeout-aware)
│   └── opa.py            # Optional OPA/Rego validator (lazy import)
├── adapters/             # one file per integration; ship with one in 0.1
│   └── <D6-choice>.py
├── cli/
│   └── inspect.py        # `commitgate events`, `commitgate replay`
└── tests/
```

Layer rules per PLAYBOOK §2 (commitgate mapping):

```
cli/  →  boundary  →  { validators/, store/, adapters/ }  →  core/ (Proposal, Validator, Result)
```

Layer-rule grep gates (PLAYBOOK §4 commitgate variant):

```bash
# G1. core/ must not import upward
grep -rn "commitgate\.\(boundary\|validators\|store\|adapters\|cli\)" commitgate/core/

# G2. store/ + validators/ + adapters/ must not import cli/
grep -rn "commitgate\.cli" commitgate/store/ commitgate/validators/ commitgate/adapters/

# G3. Only Boundary writes to the event store
grep -rn "EventStore\|event_store" commitgate/ --include="*.py" | grep -v "commitgate/store/" | grep -v "commitgate/core/boundary"

# G4. Schemas (proposal.py, result.py) must have no commitgate-internal imports
grep -rn "from commitgate" commitgate/core/proposal.py commitgate/core/result.py
```

All four must return zero matches before each commit.

---

## 4. Weekly slices

### Week 1 — Core primitives + carve

| ID | Task | Effort |
|---|---|---|
| PA1.01 | Carve `EventStore` from forge-os `events/store.py` (record source SHA in commit msg) | S |
| PA1.02 | Carve generic `Event` model from `events/model.py`; strip forge-specific event types | S |
| PA1.03 | Carve atomic-write helper from forge-os core | S |
| PA1.04 | Define `Proposal` base class | S |
| PA1.05 | Define `Validator` protocol + 3 composers (`schema`, `predicate`, `command`) | M |
| PA1.06 | Define `Executor` protocol | S |
| PA1.07 | Implement `Boundary.commit()` — validator chain + commit-or-reject + event append | M |
| PA1.08 | 25+ unit tests covering primitives | M |
| PA1.09 | First-pass typing: `mypy --strict commitgate/core/` clean | S |
| PA1.10 | Initial `pyproject.toml`; `pip install -e .[dev]` works | S |

**Week 1 exit:** `from commitgate import Boundary, Proposal, Validator` works; tests pass; one toy example commits a `WriteFile` proposal end-to-end.

### Week 2 — Replay + recorded effects + CLI

| ID | Task | Effort |
|---|---|---|
| PA1.11 | Implement `Boundary.record()` — capture non-deterministic effects (LLM calls, external API responses) | M |
| PA1.12 | Implement `Boundary.replay()` — bit-identical for deterministic events; cached return for recorded effects | M |
| PA1.13 | Property-based tests for replay determinism (`hypothesis`) | M |
| PA1.14 | CLI: `commitgate events tail/show` | S |
| PA1.15 | CLI: `commitgate replay --until-event N` | S |
| PA1.16 | Document the determinism boundary (one focused README section) | S |
| PA1.17 | 50+ tests total; PLAYBOOK §6 checklist applied per commit | — |

**Week 2 exit:** replay demo recordable + reproducible; CLI lets you inspect any event stream and replay it.

### Week 3 — One adapter + ship

| ID | Task | Effort |
|---|---|---|
| PA1.18 | Implement first adapter per D6 (default: Claude Code `PreToolUse` hook, ~60 LOC shim) | M |
| PA1.19 | End-to-end integration test: agent → adapter → Boundary → file change | M |
| PA1.20 | Demo writeup: deny-on-secret validator catching an `Edit` of a file with `AWS_SECRET_KEY=...` | M |
| PA1.21 | README, install docs, one example folder | M |
| PA1.22 | PyPI publish — 0.1.0 to TestPyPI, smoke install, then PyPI proper | S |
| PA1.23 | Launch post (Hacker News / Reddit / X / direct DM to D4 user) | S |
| PA1.24 | Activate D8 kill-criterion stopwatch — start day-counter | — |

**Week 3 exit:** `pip install commitgate` works; demo runs; D4 user has the install command.

---

## 5. Acceptance criteria

- [ ] `pip install commitgate` works on Linux + macOS (Windows best-effort).
- [ ] 50+ tests pass, including hypothesis property tests for replay determinism.
- [ ] One adapter (D6 choice) produces a working end-to-end demo.
- [ ] No runtime dependency on Forge OS code (clean carve, not a soft fork).
- [ ] PLAYBOOK §6 commit checklist applied per commit; PLAYBOOK §2 commitgate layer mapping enforced (§3 grep gates clean).
- [ ] Carved files (`events/store.py`, `events/model.py`, atomic-write helper) preserved with the source SHA recorded in their copying commit message.
- [ ] `Boundary.replay()` is bit-identical for deterministic-only event chains (property-based proven).

## 6. Exit checklist

- [ ] All PA1.xx tasks complete.
- [ ] commitgate v0.1.0 published on PyPI.
- [ ] D4 user installed and ran the demo (success or specific friction reported back).
- [ ] D8 kill-criterion stopwatch active.
- [ ] `STATUS.md` updated with launch date; new row in change log.
- [ ] forge-os fate (D7) executed: consumer mode (private dogfood) or archive (STATUS.md + freeze tag + redirect).

## 7. Out of scope (explicitly)

- LangGraph adapter (Week 4+ if 0.1 shows signal; otherwise drop).
- AutoGen adapter (same).
- MCP server (same).
- OPA validator beyond a lazy-import scaffold (Week 4+).
- Multi-process / multi-host event store (single-process, single-host for 0.1).
- UI / dashboard (out of scope; CLI is the interface).

## 8. Risks (with mitigation)

| Risk | Mitigation |
|---|---|
| Naming conflict on PyPI | Check before Week 1; alternative names: `actboundary`, `pve`. |
| Anthropic / LangGraph adds this primitive natively in 6 months | Ship fast; D8 forces a 30-day decision; if killed, the carved code still helps forge-os Fork B. |
| Validator-chain ordering surprises (e.g., command validator races) | Property-based tests for chain semantics; document ordering rules in core/validator.py. |
| The "no users" problem doesn't vanish | D4 + D8 force adoption signal as kill criterion; not vanity metrics. |

## 9. Why this phase exists

`SRSv4.1.md` §1.7 ("Bounded Autonomy Principle") + §3.33 ("Determinism Boundary Specification") describe a Proposal → Validator → Executor primitive. Forge OS v4 wraps this primitive in a 27-month enterprise SDLC scaffold. **commitgate ships the primitive as a 3-week library** — same primitive, different package boundary, no enterprise scope. Of all v4 ideas this is the one with no existing equivalent in the agent-tooling ecosystem; that's the gap commitgate fills.

---

## 10. Kill criterion (D8 — fill before Week 1)

```
Track:    commitgate v0.1
Kill date: <Week 3 ship date + 30 days>
Kill if any of:
  - PyPI installs (>7 days, non-author)            < ___
  - GitHub stars                                    < ___
  - Issues filed by non-author                      < ___
  - D4 named user successfully ran demo             < 1
  - Any reviewer reports the demo as confusing      ≥ 2 without obvious fix
Owner:           <single named human>
Review:          day 14, day 30
```

## 11. Suggested next prompt

After D4-D9 all resolved:

> `Read plan/fork-a/PHASE-A1-commitgate-extract.md and begin Week 1: PA1.01-PA1.04. One commit per task. Record source SHA when carving from forge-os.`
