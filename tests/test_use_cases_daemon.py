"""Tests for forge_os.use_cases.daemon (P10.04)."""

from __future__ import annotations

from pathlib import Path

from forge_os.daemon.state import DaemonStateStore
from forge_os.use_cases.daemon import DaemonUseCases


def test_status_shape_when_no_daemon(tmp_path: Path) -> None:
    use_cases = DaemonUseCases(tmp_path, forge_dir=tmp_path / "forge-home")

    status = use_cases.status()

    assert status == {
        "running": False,
        "pid": None,
        "started_at": None,
        "last_heartbeat": None,
        "tasks": {},
        "alerts": [],
        "log_path": str(tmp_path / "forge-home" / "daemon" / "daemon.log"),
        "stale_state": False,
    }


def test_stop_returns_stopped_false_when_nothing_running(tmp_path: Path) -> None:
    use_cases = DaemonUseCases(tmp_path, forge_dir=tmp_path / "forge-home")

    assert use_cases.stop() == {"stopped": False}


def test_logs_returns_empty_list_when_log_missing(tmp_path: Path) -> None:
    use_cases = DaemonUseCases(tmp_path, forge_dir=tmp_path / "forge-home")

    assert use_cases.logs() == []


def test_logs_returns_tail_of_log_file(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"
    store = DaemonStateStore(forge_dir=forge_dir)
    store.daemon_dir.mkdir(parents=True)
    lines = [f"line-{index}" for index in range(60)]
    _ = store.log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    use_cases = DaemonUseCases(tmp_path, forge_dir=forge_dir)

    tail = use_cases.logs(limit=50)

    assert len(tail) == 50
    assert tail[0] == "line-10"
    assert tail[-1] == "line-59"


def test_logs_with_non_positive_limit_returns_empty(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"
    store = DaemonStateStore(forge_dir=forge_dir)
    store.daemon_dir.mkdir(parents=True)
    _ = store.log_path.write_text("line\n", encoding="utf-8")
    use_cases = DaemonUseCases(tmp_path, forge_dir=forge_dir)

    assert use_cases.logs(limit=0) == []
