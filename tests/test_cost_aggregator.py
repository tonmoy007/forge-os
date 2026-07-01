"""Tests for CostAggregator (daemon-monitor S4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.cost.aggregator import CostAggregator, CostTotals
from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Cost", profile="minimal")
    return tmp_path


def _seed(root: Path, run_id: str, cost: object, adapter: str = "claude_code") -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(
        run_id,
        "AdapterSpawnCompleted",
        {"adapter": adapter, "metadata": {"total_cost_usd": cost}},
    )
    store.close()


class TestCostAggregator:
    def test_no_events_totals_zero(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        totals = CostAggregator(root).totals()
        assert totals == CostTotals(total_cost_usd=None, priced_spawns=0, total_spawns=0)
        # Read-only/alert-only: reading a never-spawned project must NOT create
        # events.db (EventStore.__init__ would mkdir + CREATE TABLE on construction).
        assert not (root / ".forge" / "events.db").exists()

    def test_non_finite_or_negative_cost_is_skipped(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 0.05)  # valid
        _seed(root, "r2", float("nan"))  # corrupt — must not poison the total
        _seed(root, "r3", float("inf"))  # corrupt
        _seed(root, "r4", -10.0)  # negative — must not mask real spend
        totals = CostAggregator(root).totals()
        assert totals.total_cost_usd == pytest.approx(0.05)
        assert totals.priced_spawns == 1
        assert totals.total_spawns == 4

    def test_sums_priced_spawns(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 0.01)
        _seed(root, "r2", 0.02)
        totals = CostAggregator(root).totals()
        assert totals.total_cost_usd == pytest.approx(0.03)
        assert totals.priced_spawns == 2
        assert totals.total_spawns == 2

    def test_unpriced_spawn_counted_but_not_summed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 0.01)
        _seed(root, "r2", None)  # adapter with no pricing
        totals = CostAggregator(root).totals()
        assert totals.total_cost_usd == pytest.approx(0.01)
        assert totals.priced_spawns == 1
        assert totals.total_spawns == 2

    def test_all_unpriced_totals_none(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", None)
        totals = CostAggregator(root).totals()
        assert totals.total_cost_usd is None
        assert totals.priced_spawns == 0
        assert totals.total_spawns == 1

    def test_bool_cost_is_not_summed(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        # bool is an int subclass — must not be treated as a $ amount.
        _seed(root, "r1", True)
        totals = CostAggregator(root).totals()
        assert totals.total_cost_usd is None
        assert totals.priced_spawns == 0
        assert totals.total_spawns == 1

    def test_corrupt_events_db_degrades_to_zero(self, tmp_path: Path) -> None:
        # A present-but-unreadable events.db must degrade like a missing one, not
        # crash the caller: the daemon self-throttle reads this from inside a
        # scheduled task, where an unhandled raise is recorded as a failure every
        # cycle. Guards both the S5 throttle and the S4 cost-cap checker.
        root = _project(tmp_path)
        (root / ".forge" / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        totals = CostAggregator(root).totals()  # must not raise
        assert totals == CostTotals(total_cost_usd=None, priced_spawns=0, total_spawns=0)
