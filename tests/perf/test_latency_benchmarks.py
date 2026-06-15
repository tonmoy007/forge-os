"""NFR latency/throughput benchmarks (P12.06-08, SRS §5.1).

Each test records a machine-readable number via pytest-benchmark and asserts the
SRS §5.1 NFR target, so a regression that blows the budget fails the perf run.
Marked ``perf`` — deselected by default; run with ``pytest tests/perf -m perf``.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from forge_os.context.pruner import ContextPruner
from forge_os.core.state_manager import StateManager
from forge_os.events import EventBus, new_event
from forge_os.hooks import HookRegistry
from forge_os.project.scaffold import initialize_project

pytestmark = pytest.mark.perf

# SRS §5.1 NFR targets.
NFR_HOOK_LATENCY_S = 0.200       # NF-P-01: hook dispatch < 200ms
NFR_CONTEXT_INJECT_S = 0.500     # NF-P-02: context injection < 500ms
NFR_CONTEXT_TOKEN_BUDGET = 2000  # NF-P-02: injected context <= 2000 tokens
NFR_STAGE_ADVANCE_S = 1.000      # NF-P-03: a stage transition well under 1s


def test_hook_dispatch_latency(benchmark, tmp_path: Path) -> None:
    registry = HookRegistry()
    registry.register("StageStarted", lambda event: None, name="noop")
    bus = EventBus(tmp_path / "events.jsonl", registry)

    benchmark(lambda: bus.emit(new_event("StageStarted", stage_id="srs")))

    assert benchmark.stats.stats.mean < NFR_HOOK_LATENCY_S


def test_context_injection_latency_and_tokens(benchmark, bench_project: Path) -> None:
    pruner = ContextPruner(bench_project)

    selection = benchmark(lambda: pruner.select("srs", token_budget=NFR_CONTEXT_TOKEN_BUDGET))

    assert benchmark.stats.stats.mean < NFR_CONTEXT_INJECT_S
    assert selection.total_tokens <= NFR_CONTEXT_TOKEN_BUDGET


def test_stage_advance_throughput(benchmark, tmp_path: Path) -> None:
    counter = itertools.count()

    def setup() -> tuple[tuple[Path], dict]:
        # Each round advances a fresh project once (setup is not timed), so the
        # measurement is pure single-transition latency — its inverse is the
        # sustained stages/sec throughput recorded in the baseline.
        root = tmp_path / f"adv-{next(counter)}"
        initialize_project(root, project_name="Bench", profile="minimal")
        _ = (root / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
        return (root,), {}

    def advance(root: Path) -> None:
        StateManager.for_project(root).advance()

    benchmark.pedantic(advance, setup=setup, rounds=20)

    assert benchmark.stats.stats.mean < NFR_STAGE_ADVANCE_S
