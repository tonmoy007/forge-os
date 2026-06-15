# Forge OS — Performance Baseline (2026-06-15)

First performance baseline (Phase 12, P12.13). Captured with:

```bash
pytest tests/perf -m perf --benchmark-json=perf.json
```

The benchmarks **assert** their SRS §5.1 NFR targets, so the `perf` CI workflow
(`.github/workflows/perf.yml`) re-runs them on a schedule and fails if a budget
is blown — this is the regression guard.

**Host:** Python 3.12.3, Intel Core i5-8400 @ 2.80GHz (a commodity dev box).

| Benchmark | NFR (SRS §5.1) | Mean | Median | Throughput | Headroom |
|---|---|---|---|---|---|
| Hook dispatch (`test_hook_dispatch_latency`) | NF-P-01 < 200ms | 0.257 ms | 0.248 ms | ~3900/s | ~780× |
| Context injection (`test_context_injection_latency_and_tokens`) | NF-P-02 < 500ms, ≤2000 tok | 0.383 ms | 0.332 ms | ~2600/s | ~1300× |
| Stage transition (`test_stage_advance_throughput`) | NF-P-03 < 1s | 45.9 ms | 42.5 ms | ~22/s | ~22× |

All targets met with large headroom on commodity hardware.

## Deferred (with rationale)

- **NF-D-001/002 — daemon idle RAM + dream-cycle cost (P12.09):** deferred.
  Measuring resident memory requires process-introspection tooling (psutil /
  `resource`) not otherwise needed pre-1.0, and the daemon is optional and not
  yet run at scale. Re-measure before making the daemon on-by-default. (L008)
- **Run-over-run regression detector (part of P12.12):** the benchmarks assert
  absolute NFR thresholds, which is the regression guard. A delta-vs-stored-
  baseline detector (persisting and diffing JSON across runs) is deferred as
  premature for a single-maintainer pre-1.0 project. (L008)
