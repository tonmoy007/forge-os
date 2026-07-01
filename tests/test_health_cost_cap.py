"""Tests for CostCapHealthChecker (FR-COST-004, daemon-monitor S4)."""

from __future__ import annotations

from pathlib import Path

import yaml

from forge_os.events.store import EventStore
from forge_os.health.cost_cap import CostCapHealthChecker
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.health import HealthUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Cost", profile="minimal")
    return tmp_path


def _seed(root: Path, run_id: str, cost: float) -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(run_id, "AdapterSpawnCompleted", {"metadata": {"total_cost_usd": cost}})
    store.close()


class TestCostCapHealthChecker:
    def test_no_cap_configured_is_healthy(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 100.0)  # spent a lot, but no cap ⇒ inert
        result = CostCapHealthChecker(root).check()
        assert result.healthy is True
        assert "No cost cap" in result.message

    def test_within_cap_is_healthy(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 1.0)  # 10% of 10
        result = CostCapHealthChecker(root, cost_cap_usd=10.0).check()
        assert result.healthy is True
        assert "within" in result.message
        assert result.details["spent_usd"] == 1.0

    def test_exact_warn_boundary_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 8.0)  # exactly 80% ⇒ inclusive "approaching"
        result = CostCapHealthChecker(root, cost_cap_usd=10.0).check()
        assert result.healthy is False
        assert "approaching" in result.message

    def test_approaching_cap_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 8.5)  # 85% ≥ 80%
        result = CostCapHealthChecker(root, cost_cap_usd=10.0).check()
        assert result.healthy is False
        assert "approaching" in result.message
        assert result.details["ratio"] == 0.85
        assert result.recommendations

    def test_over_cap_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 12.0)  # 120% ⇒ over
        result = CostCapHealthChecker(root, cost_cap_usd=10.0).check()
        assert result.healthy is False
        assert "over" in result.message

    def test_cap_resolved_from_config(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "r1", 9.0)
        # No health_monitor section ⇒ uncapped ⇒ healthy.
        assert CostCapHealthChecker(root).check().healthy is True
        # Configure a $10 cap ⇒ 9.0 is 90% ⇒ approaching ⇒ flagged.
        config_path = root / ".forge" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["features"]["health_monitor"] = {"enabled": True, "cost_cap_usd": 10.0}
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        flagged = CostCapHealthChecker(root).check()
        assert flagged.healthy is False
        assert flagged.details["cost_cap_usd"] == 10.0

    def test_unreadable_store_is_unhealthy_when_capped(self, tmp_path: Path) -> None:
        # A corrupt events.db under a cap means spend is unknown: the checker must
        # report unhealthy, not a misleading "within cap", so a defeated control
        # is visible rather than masked.
        root = _project(tmp_path)
        (root / ".forge" / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        result = CostCapHealthChecker(root, cost_cap_usd=10.0).check()
        assert result.healthy is False
        assert "unreadable" in result.message

    def test_unreadable_store_ignored_when_uncapped(self, tmp_path: Path) -> None:
        # No cap ⇒ nothing to enforce, so store readability is irrelevant.
        root = _project(tmp_path)
        (root / ".forge" / "events.db").write_bytes(b"not a sqlite database\x00\xff")
        result = CostCapHealthChecker(root).check()
        assert result.healthy is True
        assert "No cost cap" in result.message

    def test_surfaces_in_full_health_report(self, tmp_path: Path) -> None:
        report = HealthUseCases(_project(tmp_path)).run_full_check()
        assert "cost_cap" in report
        assert report["cost_cap"]["healthy"] is True  # no cap ⇒ healthy
