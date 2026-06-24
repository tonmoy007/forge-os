"""Tests for CostUseCases (FR-TE-001/004, FR-COST-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.cost import CostUseCases, _as_stage, _decode, _round_cost


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Cost", profile="minimal")
    return tmp_path


def _seed(
    root: Path,
    run_id: str,
    *,
    stage: str | None,
    input_tokens: int,
    output_tokens: int,
    cost: float | None,
    adapter: str = "claude_code",
) -> None:
    store = EventStore(root / ".forge" / "events.db")
    if stage is not None:
        store.append(run_id, "AdapterSpawnStarted", {"adapter": adapter, "stage_id": stage})
    store.append(
        run_id,
        "AdapterSpawnCompleted",
        {
            "adapter": adapter,
            "metadata": {
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                "total_cost_usd": cost,
            },
        },
    )
    store.close()


class TestReport:
    def test_empty_project(self, tmp_path: Path) -> None:
        report = CostUseCases(_project(tmp_path)).report()
        assert report.stages == []
        assert report.production_spawns == 0
        assert report.total_cost_usd is None
        assert "no data source" in report.evolution_note

    def test_aggregates_by_stage(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", stage="build", input_tokens=100, output_tokens=50, cost=0.01)
        _seed(root, "r2", stage="build", input_tokens=200, output_tokens=80, cost=0.02)
        _seed(root, "r3", stage="srs", input_tokens=10, output_tokens=5, cost=0.001)
        report = CostUseCases(root).report()
        by_stage = {s.stage_id: s for s in report.stages}
        assert by_stage["build"].spawns == 2
        assert by_stage["build"].input_tokens == 300
        assert by_stage["build"].output_tokens == 130
        assert by_stage["build"].total_tokens == 430
        assert by_stage["build"].cost_usd == pytest.approx(0.03)
        assert report.production_spawns == 3
        assert report.total_tokens == 445
        assert report.total_cost_usd == pytest.approx(0.031)
        assert report.adapters == ["claude_code"]

    def test_stage_filter(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", stage="build", input_tokens=100, output_tokens=50, cost=0.01)
        _seed(root, "r2", stage="srs", input_tokens=10, output_tokens=5, cost=0.001)
        report = CostUseCases(root).report(stage_filter="build")
        assert [s.stage_id for s in report.stages] == ["build"]
        assert report.production_spawns == 1

    def test_missing_pricing_is_none_not_zero(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", stage="build", input_tokens=100, output_tokens=50, cost=None)
        report = CostUseCases(root).report()
        assert report.stages[0].cost_usd is None
        assert report.total_cost_usd is None

    def test_partial_pricing_sums_present_only(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", stage="build", input_tokens=100, output_tokens=50, cost=0.01)
        _seed(root, "r2", stage="build", input_tokens=100, output_tokens=50, cost=None)
        report = CostUseCases(root).report()
        assert report.stages[0].spawns == 2
        assert report.stages[0].cost_usd == pytest.approx(0.01)

    def test_unattributed_when_no_started(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "orphan", stage=None, input_tokens=5, output_tokens=5, cost=0.001)
        report = CostUseCases(root).report()
        assert report.stages[0].stage_id == "(unattributed)"

    def test_started_with_none_stage_is_unattributed(self, tmp_path: Path) -> None:
        # A Started event present but with stage_id=None must bucket as unattributed.
        root = _project(tmp_path)
        store = EventStore(root / ".forge" / "events.db")
        store.append("r1", "AdapterSpawnStarted", {"adapter": "claude_code", "stage_id": None})
        store.append(
            "r1",
            "AdapterSpawnCompleted",
            {"adapter": "claude_code", "metadata": {"usage": {}, "total_cost_usd": None}},
        )
        store.close()
        report = CostUseCases(root).report()
        assert [s.stage_id for s in report.stages] == ["(unattributed)"]

    def test_stages_sorted_deterministically(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", stage="srs", input_tokens=10, output_tokens=5, cost=0.001)
        _seed(root, "r2", stage="build", input_tokens=10, output_tokens=5, cost=0.001)
        report = CostUseCases(root).report()
        assert [s.stage_id for s in report.stages] == ["build", "srs"]

    def test_per_stage_cost_is_rounded(self, tmp_path: Path) -> None:
        # Per-stage cost must be rounded like the total, not leak FP noise into JSON.
        root = _project(tmp_path)
        for run in ("r1", "r2", "r3"):
            _seed(root, run, stage="build", input_tokens=1, output_tokens=1, cost=0.1)
        report = CostUseCases(root).report()
        assert report.stages[0].cost_usd == 0.3  # not 0.30000000000000004
        assert report.total_cost_usd == 0.3


class TestRobustness:
    def test_read_only_does_not_create_events_db(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        report = CostUseCases(root).report()
        assert report.stages == []
        assert not (root / ".forge" / "events.db").exists()

    def test_degrades_on_malformed_rows(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "good", stage="build", input_tokens=100, output_tokens=50, cost=0.01)
        store = EventStore(root / ".forge" / "events.db")
        # non-string stage_id (would crash sorted()) + non-dict metadata (AttributeError)
        store.append("weird", "AdapterSpawnStarted", {"adapter": "claude_code", "stage_id": 42})
        store.append("weird", "AdapterSpawnCompleted", {"adapter": "claude_code", "metadata": "x"})
        # a genuinely malformed-JSON row (bypasses append's json.dumps)
        conn = store._connect()
        conn.execute(
            "INSERT INTO events (stream_id, event_type, payload, version) VALUES (?, ?, ?, ?)",
            ("bad", "AdapterSpawnCompleted", "{not json", 99),
        )
        conn.commit()
        store.close()

        report = CostUseCases(root).report()  # must not raise
        by_stage = {s.stage_id: s for s in report.stages}
        assert by_stage["build"].spawns == 1  # valid data preserved
        assert "(unattributed)" in by_stage  # int-stage spawn bucketed safely
        assert report.production_spawns == 2  # malformed-JSON row skipped


class TestHelpers:
    def test_decode_skips_bad_json_and_non_objects(self) -> None:
        assert _decode('{"a": 1}') == {"a": 1}
        assert _decode("{not json") is None
        assert _decode('"a string"') is None  # valid JSON but not an object
        assert _decode(123) is None

    def test_as_stage_coerces_to_str_or_none(self) -> None:
        assert _as_stage("build") == "build"
        assert _as_stage(42) is None
        assert _as_stage(None) is None

    def test_round_cost(self) -> None:
        assert _round_cost(0.30000000000000004) == 0.3
        assert _round_cost(None) is None
