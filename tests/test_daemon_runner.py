"""Tests for forge_os.daemon.runner (P10.03)."""

from __future__ import annotations

import os
import signal
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge_os.daemon.runner import main
from forge_os.daemon.state import DaemonStateStore


@pytest.fixture
def restore_signal_handlers() -> Iterator[None]:
    term = signal.getsignal(signal.SIGTERM)
    intr = signal.getsignal(signal.SIGINT)
    yield
    _ = signal.signal(signal.SIGTERM, term)
    _ = signal.signal(signal.SIGINT, intr)


def test_main_persists_state_runs_heartbeat_and_exits_on_sigterm(
    tmp_path: Path, restore_signal_handlers: None
) -> None:
    forge_dir = tmp_path / "forge-home"
    timer = threading.Timer(0.2, os.kill, args=(os.getpid(), signal.SIGTERM))
    timer.start()

    try:
        exit_code = main([str(tmp_path), "--forge-dir", str(forge_dir)])
    finally:
        timer.cancel()

    assert exit_code == 0
    state = DaemonStateStore(forge_dir=forge_dir).load()
    assert state is not None
    assert state.pid == os.getpid()
    assert state.daemon_id.startswith("daemon-")
    assert state.project_root == str(tmp_path.resolve())
    assert state.last_heartbeat is not None
    assert state.tasks["heartbeat"].runs >= 1
    assert state.tasks["heartbeat"].last_status == "ok"
    assert (forge_dir / "daemon" / "daemon.log").read_text(encoding="utf-8") != ""


def test_main_rejects_missing_project_root_argument() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _ = main([])

    assert excinfo.value.code == 2
