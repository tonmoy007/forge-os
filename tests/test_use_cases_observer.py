"""Tests for forge_os.use_cases.observer (P10.10-14)."""

from __future__ import annotations

from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.observer.monitor import ObserverMonitor
from forge_os.schemas.daemon import DaemonState
from forge_os.schemas.observer import ObserverConfig
from forge_os.use_cases.observer import ObserverUseCases

NOW = "2026-06-10T12:00:00Z"


class FakeRegistry:
    def __init__(self, *, accessible: bool = True, agents: list[dict] | None = None) -> None:
        self.accessible = accessible
        self.agents = agents or []

    def is_registry_accessible(self) -> bool:
        return self.accessible

    def get_installed_agents(self) -> list[dict]:
        return list(self.agents)


def make_use_cases(
    tmp_path: Path, *, accessible: bool = True, agents: list[dict] | None = None
) -> ObserverUseCases:
    forge_dir = tmp_path / "forge"
    monitor = ObserverMonitor(
        tmp_path / "project",
        forge_dir,
        now=lambda: NOW,
        config=ObserverConfig(enabled=True),
        registry=FakeRegistry(accessible=accessible, agents=agents),  # type: ignore[arg-type]
        client_factory=lambda command: None,
    )
    return ObserverUseCases(tmp_path / "project", forge_dir, monitor=monitor)


def seed_daemon_state(forge_dir: Path) -> None:
    DaemonStateStore(forge_dir).save(
        DaemonState(
            daemon_id="daemon-test",
            pid=4321,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )


def test_status_with_no_metrics_or_daemon_state(tmp_path: Path) -> None:
    use_cases = make_use_cases(tmp_path)

    result = use_cases.status()

    assert result["config"]["enabled"] is True
    assert result["metrics"] is None
    assert result["alerts"] == []


def test_run_checks_with_no_installed_agents(tmp_path: Path) -> None:
    use_cases = make_use_cases(tmp_path)

    result = use_cases.run_checks()

    assert result["registry"] == {"accessible": True, "alerted": False}
    assert result["sessions"] == {"checked": 0, "closed": 0, "errors": 0}
    assert result["metrics"]["collected_at"] == NOW


def test_status_surfaces_metrics_and_alerts_after_run_checks(tmp_path: Path) -> None:
    seed_daemon_state(tmp_path / "forge")
    use_cases = make_use_cases(tmp_path, accessible=False)

    _ = use_cases.run_checks()
    result = use_cases.status()

    assert result["metrics"] is not None
    assert result["metrics"]["collected_at"] == NOW
    assert len(result["alerts"]) == 1
    assert result["alerts"][0]["source"] == "acp-registry"
    assert result["alerts"][0]["severity"] == "warning"
