"""Tests for forge_os.daemon.tasks (P10.02)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.daemon.tasks import HEARTBEAT_INTERVAL_SECONDS, build_scheduled_tasks
from forge_os.schemas.daemon import DaemonState


def seed_state(store: DaemonStateStore) -> None:
    store.save(
        DaemonState(
            daemon_id="daemon-test",
            pid=4321,
            project_root="/tmp/project",
            started_at="2026-06-10T00:00:00Z",
        )
    )


def test_build_returns_heartbeat_task_with_30s_interval(tmp_path: Path) -> None:
    tasks = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")

    assert [task.name for task in tasks] == ["heartbeat"]
    assert tasks[0].interval_seconds == HEARTBEAT_INTERVAL_SECONDS == 30.0


def test_heartbeat_updates_last_heartbeat_in_store(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    store = DaemonStateStore(forge_dir=forge_dir)
    seed_state(store)
    heartbeat = build_scheduled_tasks(tmp_path, forge_dir=forge_dir)[0]

    result = heartbeat.run()

    reloaded = store.load()
    assert reloaded is not None
    assert reloaded.last_heartbeat is not None
    assert result == {"last_heartbeat": reloaded.last_heartbeat}


def test_heartbeat_raises_daemon_state_error_when_state_missing(tmp_path: Path) -> None:
    heartbeat = build_scheduled_tasks(tmp_path, forge_dir=tmp_path / "forge")[0]

    with pytest.raises(DaemonStateError, match="heartbeat cannot update"):
        _ = heartbeat.run()
