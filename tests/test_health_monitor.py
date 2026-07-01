"""Tests for the always-on HealthMonitor sweep (daemon-monitor S6)."""

from __future__ import annotations

from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.health.monitor import HealthMonitor
from forge_os.schemas.daemon import DaemonState


class _StubChecker(HealthChecker):
    def __init__(
        self, result: HealthResult | None = None, *, raises: Exception | None = None
    ) -> None:
        self._result = result
        self._raises = raises

    def check(self) -> HealthResult:
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _healthy() -> HealthResult:
    return HealthResult(healthy=True, message="fine")


def _unhealthy(message: str = "too slow") -> HealthResult:
    return HealthResult(healthy=False, message=message, recommendations=["do X"])


def _store_with_state(forge_dir: Path) -> DaemonStateStore:
    store = DaemonStateStore(forge_dir)
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=1234,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )
    return store


def _monitor(tmp_path: Path, checkers: dict[str, HealthChecker]) -> HealthMonitor:
    forge_dir = tmp_path / "forge"
    _store_with_state(forge_dir)
    return HealthMonitor(tmp_path, forge_dir, checkers=checkers)


class TestHealthMonitor:
    def test_all_healthy_records_no_alert(self, tmp_path: Path) -> None:
        monitor = _monitor(tmp_path, {"a": _StubChecker(_healthy()), "b": _StubChecker(_healthy())})
        result = monitor.check()
        assert result == {"checked": 2, "unhealthy": 0, "alerted": 0}
        reloaded = DaemonStateStore(tmp_path / "forge").load()
        assert reloaded is not None and reloaded.alerts == []

    def test_unhealthy_checker_raises_one_alert(self, tmp_path: Path) -> None:
        monitor = _monitor(
            tmp_path,
            {
                "hook_latency": _StubChecker(_unhealthy("hooks slow")),
                "cost_cap": _StubChecker(_healthy()),
            },
        )
        result = monitor.check()
        assert result == {"checked": 2, "unhealthy": 1, "alerted": 1}
        alerts = DaemonStateStore(tmp_path / "forge").load().alerts
        assert len(alerts) == 1
        assert alerts[0].source == "health-hook_latency"
        assert alerts[0].severity == "warning"
        assert alerts[0].message == "hooks slow"
        assert alerts[0].metadata["checker"] == "hook_latency"
        assert alerts[0].metadata["recommendations"] == ["do X"]

    def test_crashing_checker_is_isolated(self, tmp_path: Path) -> None:
        # One checker raising must not abort the sweep or the scheduled task.
        monitor = _monitor(
            tmp_path,
            {"boom": _StubChecker(raises=RuntimeError("kaboom")), "ok": _StubChecker(_healthy())},
        )
        result = monitor.check()  # must not raise
        assert result == {"checked": 1, "unhealthy": 0, "alerted": 0}  # crash not counted

    def test_missing_daemon_state_is_best_effort(self, tmp_path: Path) -> None:
        # No state saved ⇒ add_alert raises DaemonStateError; the monitor swallows
        # it so a health sweep never becomes a task failure.
        monitor = HealthMonitor(
            tmp_path, tmp_path / "forge", checkers={"x": _StubChecker(_unhealthy())}
        )
        result = monitor.check()  # must not raise
        assert result == {"checked": 1, "unhealthy": 1, "alerted": 0}
        assert DaemonStateStore(tmp_path / "forge").load() is None

    def test_repeated_unhealthy_dedups(self, tmp_path: Path) -> None:
        monitor = _monitor(tmp_path, {"cost_cap": _StubChecker(_unhealthy("over cap"))})
        _ = monitor.check()
        _ = monitor.check()
        alerts = DaemonStateStore(tmp_path / "forge").load().alerts
        assert len(alerts) == 1  # add_alert suppresses the consecutive duplicate

    def test_default_checkers_are_the_monitor_subset(self, tmp_path: Path) -> None:
        # Real (uninjected) monitor uses exactly hook_latency/token_budget/cost_cap.
        monitor = HealthMonitor(tmp_path, tmp_path / "forge")
        assert set(monitor._checkers) == {"hook_latency", "token_budget", "cost_cap"}
