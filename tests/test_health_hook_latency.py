"""Tests for HookLatencyHealthChecker (FR-HD-005)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from forge_os.health.checker import HealthResult
from forge_os.health.hook_latency import HookLatencyHealthChecker
from forge_os.hooks.timing import HookTiming, HookTimingLog
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.health import HealthUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


def _seed(root: Path, hook_name: str, durations: list[float]) -> None:
    HookTimingLog(root / ".forge").append(
        [
            HookTiming(
                event_type="StageStarted",
                hook_name=hook_name,
                status="succeeded",
                duration_ms=duration,
            )
            for duration in durations
        ]
    )


def _check(root: Path) -> HealthResult:
    # Low threshold keeps the seeded durations small and the test deterministic.
    return HookLatencyHealthChecker(root, slow_threshold_ms=10.0, min_samples=3).check()


class TestHookLatencyHealthChecker:
    def test_no_timings_is_healthy(self, tmp_path: Path) -> None:
        result = _check(_project(tmp_path))
        assert result.healthy is True
        assert "No hook timings recorded yet" in result.message
        assert result.details["hooks_tracked"] == 0

    def test_fast_hooks_within_budget(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "fast", [1.0, 2.0, 3.0])
        result = _check(root)
        assert result.healthy is True
        assert "within latency budget" in result.message
        assert result.details["slow_hooks"] == []

    def test_persistently_slow_hook_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "slow", [20.0, 30.0, 40.0])  # mean 30 ≥ 10 over 3 samples
        result = _check(root)
        assert result.healthy is False
        assert "slow" in result.message
        slow_hooks = result.details["slow_hooks"]
        assert len(slow_hooks) == 1
        assert slow_hooks[0]["hook_name"] == "slow"
        assert slow_hooks[0]["mean_ms"] == 30.0
        assert slow_hooks[0]["max_ms"] == 40.0
        assert result.recommendations  # actionable hint present

    def test_one_off_slow_sample_below_min_samples_not_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "blip", [500.0, 1.0])  # high max but only 2 samples (< min_samples 3)
        result = _check(root)
        assert result.healthy is True
        assert result.details["slow_hooks"] == []

    def test_multiple_slow_hooks_sorted_by_mean_desc(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "mild", [11.0, 12.0, 13.0])  # mean 12
        _seed(root, "severe", [50.0, 60.0, 70.0])  # mean 60
        result = _check(root)
        assert result.healthy is False
        names = [hook["hook_name"] for hook in result.details["slow_hooks"]]
        assert names == ["severe", "mild"]

    def test_empty_surfaces_in_full_health_report(self, tmp_path: Path) -> None:
        report = HealthUseCases(_project(tmp_path)).run_full_check()
        assert "hook_latency" in report
        assert report["hook_latency"]["healthy"] is True  # nothing recorded ⇒ healthy

    def test_full_report_flags_slow_hook_at_default_threshold(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "verylslow", [2000.0, 2000.0, 2000.0])  # mean 2s ≥ default 1s, 3 samples
        report = HealthUseCases(root).run_full_check()
        assert report["hook_latency"]["healthy"] is False
        assert "verylslow" in report["hook_latency"]["message"]

    def test_mean_exactly_at_threshold_is_flagged(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        _seed(root, "edge", [10.0, 10.0, 10.0])  # mean == threshold (10.0) ⇒ inclusive flag
        result = _check(root)
        assert result.healthy is False
        assert result.details["slow_hooks"][0]["hook_name"] == "edge"

    def test_non_finite_sample_is_ignored_not_poisoning(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        # A foreign/hand-corrupted log can carry a literal NaN token: the canonical
        # writer emits null, but read_all tolerates corruption. A NaN must be ignored,
        # not poison the hook's mean and hide a genuinely slow hook.
        finite = json.dumps(
            {"event_type": "E", "hook_name": "slow", "status": "succeeded",
             "duration_ms": 20.0, "recorded_at": "t"}
        )
        nan_line = (
            '{"event_type": "E", "hook_name": "slow", "status": "succeeded", '
            '"duration_ms": NaN, "recorded_at": "t"}'
        )
        path = root / ".forge" / "hook-timings.jsonl"
        path.write_text("\n".join([finite, finite, finite, nan_line]) + "\n", encoding="utf-8")

        result = _check(root)  # threshold 10, min_samples 3
        # The 3 finite 20ms samples must still flag the hook (NaN dropped, not poisoning).
        assert result.healthy is False
        slow = result.details["slow_hooks"][0]
        assert slow["hook_name"] == "slow"
        # No non-finite value leaked into the report.
        assert math.isfinite(slow["mean_ms"])
        assert math.isfinite(slow["max_ms"])
