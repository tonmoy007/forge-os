"""Tests for forge_os.project.status.daemon_alerts (P10 WS-C)."""

from __future__ import annotations

from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.project.status import daemon_alerts
from forge_os.schemas.daemon import DaemonAlert, DaemonState


def seed_state_with_alerts(forge_dir: Path, count: int) -> None:
    store = DaemonStateStore(forge_dir)
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=4321,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
            alerts=[
                DaemonAlert(
                    alert_id=f"alert-{index}",
                    created_at=f"2026-06-10T00:00:{index:02d}Z",
                    source="acp-registry",
                    severity="warning",
                    message=f"alert {index}",
                )
                for index in range(count)
            ],
        )
    )


def test_returns_empty_list_when_state_missing(tmp_path: Path) -> None:
    assert daemon_alerts(tmp_path / "forge") == []


def test_returns_empty_list_when_state_corrupt(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    daemon_dir = forge_dir / "daemon"
    daemon_dir.mkdir(parents=True)
    (daemon_dir / "state.json").write_text("{not json", encoding="utf-8")

    assert daemon_alerts(forge_dir) == []


def test_returns_most_recent_alerts_newest_first(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    seed_state_with_alerts(forge_dir, count=7)

    alerts = daemon_alerts(forge_dir, limit=5)

    assert [a["alert_id"] for a in alerts] == [
        "alert-6",
        "alert-5",
        "alert-4",
        "alert-3",
        "alert-2",
    ]


def test_returns_all_alerts_when_fewer_than_limit(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    seed_state_with_alerts(forge_dir, count=2)

    alerts = daemon_alerts(forge_dir)

    assert [a["alert_id"] for a in alerts] == ["alert-1", "alert-0"]


def test_returns_empty_list_for_non_positive_limit(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    seed_state_with_alerts(forge_dir, count=2)

    assert daemon_alerts(forge_dir, limit=0) == []
