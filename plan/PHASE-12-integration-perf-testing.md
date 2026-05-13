# PHASE-12 — Integration & Performance Testing

> **Scope-conditional:** applies under **Fork B** (continue forge-os scoped to v2). Skip entirely if `STATUS.md` D5 resolves to Fork A (commitgate extract) or Fork C (research).
>
> **Prerequisites:** D9 baseline cleanup complete (`ruff check src tests` returns 0). Phase 10 complete.
>
> **PLAYBOOK:** apply `plan/PLAYBOOK.md` §6 (per-commit) and §7 (per-feature) checklists for every slice.

---

## 1. Objective

Establish the integration-test surface and performance-baseline harness that gate any release of forge-os. Phases 01-09 have ~230 unit tests; nothing systematically verifies cross-phase behavior or NFR targets. Without this phase, "passes tests" doesn't mean "works for users."

## 2. ADR alignment

| ADR | How this phase honors it |
|---|---|
| ADR-002 (local-first) | All integration tests run offline using DummyAdapter / HumanAdapter; no network required for CI. |
| ADR-005 (kernel adapter boundary) | Adapter-swap regression suite is the executable proof of the boundary. |
| ADR-006 (optional layers) | Tests verify daemon-off and daemon-on modes both work; no test depends on optional layers being active. |
| ADR-007 (security) | Sandbox/timeout enforcement tested via deliberately-misbehaving fixture commands. |

## 3. Scope

**In:**
- End-to-end integration tests covering `forge init` → `stage start` → gates → `stage advance` → events → reflections → lessons.
- Adapter-swap regression suite (DummyAdapter / HumanAdapter / mocked ClaudeCodeAdapter produce equivalent state.json sans actor-id).
- Performance baseline harness measuring NFR targets from `SRS.md` §5.1: hook latency <200ms, context injection <500ms, 10 concurrent projects supported.
- Golden datasets for gate evaluation (`tests/fixtures/gate_golden/{passing,failing,warning}/`).
- CI integration: integration suite on every push; perf suite nightly with regression detection.

**Out (parked or v4 scope):**
- gVisor sandbox testing (parked).
- Multi-tenancy load testing (parked).
- LLM cost benchmarking (no production AI integration under Fork B).
- Cross-host concurrent-project testing (single-host suffices for v2).

## 4. Dependencies

- Phase 10 complete (perf tests must cover daemon idle and dream-cycle costs).
- D9 cleanup complete (PLAYBOOK §6 enforces ruff-clean baseline before any commit lands).
- `pytest-benchmark` added to `pyproject.toml [project.optional-dependencies] dev`.

## 5. Deliverables

| Item | Path |
|---|---|
| Integration test suite | `tests/integration/test_*.py` |
| Adapter swap regression | `tests/integration/test_adapter_swap.py` |
| Performance harness | `tests/perf/` (separate from `tests/` so the unit suite stays fast) |
| Golden gate fixtures | `tests/fixtures/gate_golden/{passing,failing,warning}/` |
| Perf baseline report | `pipeline/log/perf-baseline-YYYY-MM-DD.md` |
| NFR target check script | `scripts/check_nfr.sh` (compares perf.json to NFR thresholds) |
| CI workflow | `.github/workflows/integration.yml` (push) + `.github/workflows/perf-nightly.yml` |

## 6. Tasks

| ID | Task | Effort | Notes |
|---|---|---|---|
| P12.01 | Add `tests/integration/conftest.py`: shared fixtures for ephemeral project dirs | S | Use `tmp_path` per Lesson L001 |
| P12.02 | 5 happy-path E2E tests: init → stage cycle → reflection → lesson | M | Per profile: minimal (3-stage), standard (12-stage) |
| P12.03 | 5 failure-path E2E tests: gate block, hook timeout, adapter failure, override audit, backtrack | M | |
| P12.04 | Adapter-swap regression suite | M | Fixture re-runs scenario across 3 adapters; asserts state-equivalence |
| P12.05 | Add `pytest-benchmark` dep + `tests/perf/conftest.py` skeleton | S | |
| P12.06 | Hook-latency benchmark | S | NF-P-01 target: <200ms p95 |
| P12.07 | Context-injection benchmark with token counting | M | NF-P-02 target: <500ms p95, <2000 tokens |
| P12.08 | Stage-transition throughput benchmark | S | Stages/sec; 10 concurrent profiles per NF-P-03 |
| P12.09 | Daemon idle + dream-cycle resource benchmark | M | RAM <200MB idle (NF-D-001 from SRSv2); cycle <10min for 200 lessons (NF-D-002) |
| P12.10 | Golden gate fixtures: ≥3 passing + 3 failing + 2 warning per gate type | M | Drive from `pipeline/gates.yaml` schema |
| P12.11 | CI: integration suite on every push (Linux) | S | |
| P12.12 | CI: perf suite nightly + regression detector (compare to last baseline) | M | Fail CI on >20% regression |
| P12.13 | First baseline report committed | S | `pipeline/log/perf-baseline-<date>.md` |

## 7. Acceptance criteria

- [ ] All NFR targets in `SRS.md` §5.1 either pass or have a written rationale (lesson) for why the gap is acceptable.
- [ ] Adapter-swap test demonstrates DummyAdapter and HumanAdapter produce identical state.json (minus actor-id).
- [ ] Golden fixtures cover every gate type defined in `pipeline/gates.yaml`.
- [ ] Integration suite runs in <60 seconds on CI (otherwise unit-suite pace degrades developer flow).
- [ ] Perf suite produces machine-readable baseline JSON comparable run-over-run.
- [ ] Nightly regression detector catches a deliberately-introduced 30% slowdown in a smoke test.

## 8. Exit checklist

- [ ] All P12.xx tasks complete.
- [ ] `.venv/bin/python -m pytest tests/integration` — green.
- [ ] `.venv/bin/python -m pytest tests/perf --benchmark-json=perf.json` — green; results within NFRs.
- [ ] PLAYBOOK §6 commit checklist applied per commit; PLAYBOOK §4 grep gates clean.
- [ ] `plan/CURRENT_PHASE.md` updated; phase marked complete.
- [ ] Lessons captured for any NFR target that needed a rationale.

## 9. Kill criterion (set before P12.01)

```
Track:    PHASE-12 integration & perf testing
Kill date: <D5-resolution date + 30 days>
Kill if any of:
  - Integration tests not started by day 14
  - NFR perf targets unachievable on commodity hardware (must record in lessons.md)
  - Phase 13 starts before Phase 12 exits (out-of-order = bug; pause and re-plan)
Owner:           <single named human>
Review cadence:  weekly
```

## 10. Suggested next prompt

After D5 = B and P12 prereqs are met:

> `Read plan/PHASE-12-integration-perf-testing.md and execute P12.01-P12.04 (integration suite scaffold + happy-path + adapter-swap). One commit per task. Update plan/CURRENT_PHASE.md when P12.04 completes.`
