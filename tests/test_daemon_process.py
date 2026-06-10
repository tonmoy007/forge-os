"""Integration tests for forge_os.daemon.process (P10.03).

The lifecycle test spawns the real runner as a short-lived child against a
tmp_path forge_dir. The child needs this worktree's `src` on PYTHONPATH so it
imports the same code under test (the editable install may point elsewhere).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge_os.daemon.process import (
    DaemonProcessError,
    daemon_status,
    is_pid_alive,
    start_daemon,
    stop_daemon,
)
from forge_os.daemon.state import DaemonStateStore
from forge_os.schemas.daemon import DaemonState

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture(autouse=True)
def child_imports_worktree_src(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    existing = os.environ.get("PYTHONPATH")
    value = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    monkeypatch.setenv("PYTHONPATH", value)
    yield


def spawn_dead_pid() -> int:
    """Return the pid of a process that has already exited and been reaped."""

    completed = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(completed.stdout.strip())


def test_is_pid_alive_true_for_own_process() -> None:
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_false_for_dead_pid() -> None:
    assert is_pid_alive(spawn_dead_pid()) is False


def test_is_pid_alive_false_for_non_positive_pid() -> None:
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False


def test_start_status_double_start_refusal_and_stop_lifecycle(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"

    state = start_daemon(tmp_path, forge_dir)
    try:
        assert is_pid_alive(state.pid) is True
        assert state.pid != os.getpid()

        status = daemon_status(forge_dir)
        assert status["running"] is True
        assert status["pid"] == state.pid
        assert status["stale_state"] is False

        with pytest.raises(DaemonProcessError, match="already running"):
            _ = start_daemon(tmp_path, forge_dir)
    finally:
        stopped = stop_daemon(forge_dir)

    assert stopped is True
    assert is_pid_alive(state.pid) is False
    after = daemon_status(forge_dir)
    assert after["running"] is False
    # State is intentionally kept on graceful stop; liveness comes from the pid probe.
    assert after["stale_state"] is True
    assert after["pid"] == state.pid


def test_daemon_status_reports_stale_state_for_dead_pid(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"
    DaemonStateStore(forge_dir=forge_dir).save(
        DaemonState(
            daemon_id="daemon-stale",
            pid=spawn_dead_pid(),
            project_root=str(tmp_path),
            started_at="2026-06-10T00:00:00Z",
        )
    )

    status = daemon_status(forge_dir)

    assert status["running"] is False
    assert status["stale_state"] is True


def test_start_daemon_replaces_stale_state_with_dead_pid(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"
    store = DaemonStateStore(forge_dir=forge_dir)
    store.save(
        DaemonState(
            daemon_id="daemon-stale",
            pid=spawn_dead_pid(),
            project_root=str(tmp_path),
            started_at="2026-06-10T00:00:00Z",
        )
    )

    state = start_daemon(tmp_path, forge_dir)
    try:
        assert state.daemon_id != "daemon-stale"
        assert is_pid_alive(state.pid) is True
    finally:
        assert stop_daemon(forge_dir) is True


def test_stop_daemon_returns_false_when_no_daemon(tmp_path: Path) -> None:
    assert stop_daemon(tmp_path / "forge-home") is False


def test_stop_daemon_returns_false_for_stale_state(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge-home"
    DaemonStateStore(forge_dir=forge_dir).save(
        DaemonState(
            daemon_id="daemon-stale",
            pid=spawn_dead_pid(),
            project_root=str(tmp_path),
            started_at="2026-06-10T00:00:00Z",
        )
    )

    assert stop_daemon(forge_dir) is False


def test_start_daemon_raises_with_log_tail_when_child_dies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "executable", "/bin/false")

    with pytest.raises(DaemonProcessError, match="exited with code"):
        _ = start_daemon(tmp_path, tmp_path / "forge-home")


def test_daemon_status_when_no_state_file(tmp_path: Path) -> None:
    status = daemon_status(tmp_path / "forge-home")

    assert status["running"] is False
    assert status["pid"] is None
    assert status["stale_state"] is False
    assert status["tasks"] == {}
    assert status["alerts"] == []


def test_start_daemon_recovers_from_zombie_child(tmp_path: Path) -> None:
    # A SIGKILLed daemon child stays a zombie (this test process is its parent
    # and has not waited on it); zombies still answer the signal-0 probe.
    # start_daemon must reap before the liveness check or restart is bricked.
    import signal as _signal

    first = start_daemon(tmp_path, forge_dir=tmp_path)
    os.kill(first.pid, _signal.SIGKILL)
    _wait_for_zombie(first.pid)

    second = start_daemon(tmp_path, forge_dir=tmp_path)
    try:
        assert second.pid != first.pid
    finally:
        _ = stop_daemon(tmp_path)


def _wait_for_zombie(pid: int, timeout: float = 5.0) -> None:
    """Poll /proc until `pid` is a zombie — without reaping it (waitpid would)."""

    import time as _time

    stat_path = Path(f"/proc/{pid}/stat")
    waited = 0.0
    while waited < timeout:
        fields = stat_path.read_text(encoding="ascii").split()
        if fields[2] == "Z":
            return
        _time.sleep(0.02)
        waited += 0.02
    raise AssertionError(f"pid {pid} did not become a zombie within {timeout}s")


def test_daemon_status_reports_corrupt_state_without_raising(tmp_path: Path) -> None:
    store = DaemonStateStore(tmp_path)
    store.daemon_dir.mkdir(parents=True, exist_ok=True)
    _ = store.state_path.write_text("{not json", encoding="utf-8")

    status = daemon_status(tmp_path)

    assert status["running"] is False
    assert status["corrupt_state"] is True
    assert "Corrupt daemon state" in status["error"]


def test_fresh_start_lock_blocks_concurrent_start(tmp_path: Path) -> None:
    store = DaemonStateStore(tmp_path)
    store.daemon_dir.mkdir(parents=True, exist_ok=True)
    lock = store.daemon_dir / "start.lock"
    _ = lock.write_text("", encoding="utf-8")  # fresh mtime

    with pytest.raises(DaemonProcessError, match="in progress"):
        _ = start_daemon(tmp_path, forge_dir=tmp_path)


def test_stale_start_lock_is_recovered(tmp_path: Path) -> None:
    store = DaemonStateStore(tmp_path)
    store.daemon_dir.mkdir(parents=True, exist_ok=True)
    lock = store.daemon_dir / "start.lock"
    _ = lock.write_text("", encoding="utf-8")
    os.utime(lock, (0, 0))  # ancient mtime -> crash leftover

    state = start_daemon(tmp_path, forge_dir=tmp_path)
    try:
        assert state.pid > 0
    finally:
        _ = stop_daemon(tmp_path)
