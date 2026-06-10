"""Daemon process lifecycle: spawn, stop, and status probing (P10.03)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge_os.daemon.state import DaemonStateStore
from forge_os.schemas.daemon import DaemonState


class DaemonProcessError(RuntimeError):
    """Raised when the daemon process cannot be started or stopped."""


def is_pid_alive(pid: int) -> bool:
    """Return True when a process with `pid` exists (signal-0 probe)."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def start_daemon(
    project_root: Path,
    forge_dir: Path | None = None,
    *,
    wait_timeout: float = 5.0,
    poll_interval: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
) -> DaemonState:
    """Spawn the daemon runner detached and wait until it persists its state."""

    store = DaemonStateStore(forge_dir)
    existing = store.load()
    if existing is not None and is_pid_alive(existing.pid):
        raise DaemonProcessError(
            f"Daemon already running (pid {existing.pid}, started {existing.started_at})."
        )

    store.daemon_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "forge_os.daemon.runner", str(project_root)]
    if forge_dir is not None:
        command += ["--forge-dir", str(forge_dir)]
    with open(store.log_path, "ab") as log_fh:
        process = subprocess.Popen(
            command,
            start_new_session=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )

    waited = 0.0
    while True:
        state = store.load()
        if state is not None and state.pid == process.pid:
            return state
        if process.poll() is not None:
            raise DaemonProcessError(
                f"Daemon process exited with code {process.returncode} before becoming "
                f"ready. Log tail:\n{_log_tail(store.log_path)}"
            )
        if waited >= wait_timeout:
            raise DaemonProcessError(
                f"Timed out after {wait_timeout}s waiting for daemon pid {process.pid} "
                f"to persist its state. Log tail:\n{_log_tail(store.log_path)}"
            )
        sleep(poll_interval)
        waited += poll_interval


def stop_daemon(
    forge_dir: Path | None = None,
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """SIGTERM the recorded daemon pid and wait for it to exit.

    Returns False when no daemon state exists or the recorded pid is already dead.
    Raises DaemonProcessError on timeout — never escalates to SIGKILL silently.
    """

    store = DaemonStateStore(forge_dir)
    state = store.load()
    if state is None or not is_pid_alive(state.pid):
        return False

    os.kill(state.pid, signal.SIGTERM)
    waited = 0.0
    while True:
        _reap_if_child(state.pid)
        if not is_pid_alive(state.pid):
            return True
        if waited >= timeout:
            raise DaemonProcessError(
                f"Daemon pid {state.pid} did not stop within {timeout}s after SIGTERM."
            )
        sleep(poll_interval)
        waited += poll_interval


def daemon_status(forge_dir: Path | None = None) -> dict[str, Any]:
    """Return a liveness/status snapshot; liveness comes from a pid probe."""

    store = DaemonStateStore(forge_dir)
    state = store.load()
    if state is None:
        return {
            "running": False,
            "pid": None,
            "started_at": None,
            "last_heartbeat": None,
            "tasks": {},
            "alerts": [],
            "log_path": str(store.log_path),
            "stale_state": False,
        }
    running = is_pid_alive(state.pid)
    return {
        "running": running,
        "pid": state.pid,
        "started_at": state.started_at,
        "last_heartbeat": state.last_heartbeat,
        "tasks": {name: task.model_dump() for name, task in state.tasks.items()},
        "alerts": [alert.model_dump() for alert in state.alerts],
        "log_path": str(store.log_path),
        "stale_state": not running,
    }


def _reap_if_child(pid: int) -> None:
    """Reap `pid` if it is a zombie child of this process.

    When the same process both starts and stops the daemon (tests, `restart`),
    the exited child stays a zombie until waited on, and `os.kill(pid, 0)` keeps
    succeeding on zombies. Non-children raise ChildProcessError, which is fine.
    """

    try:
        _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


def _log_tail(log_path: Path, lines: int = 20) -> str:
    if not log_path.exists():
        return "(no daemon log)"
    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])
