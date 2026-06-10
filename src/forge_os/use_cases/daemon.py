"""Daemon lifecycle use cases (P10.04)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.daemon.process import daemon_status, start_daemon, stop_daemon
from forge_os.daemon.state import DaemonStateStore


class DaemonUseCases:
    """Bridge between the daemon CLI and the daemon domain module.

    Domain errors (`DaemonProcessError`, `DaemonStateError`) propagate as-is;
    the CLI layer translates them into exit codes.
    """

    def __init__(self, project_root: Path, forge_dir: Path | None = None) -> None:
        self.project_root = project_root
        self.forge_dir = forge_dir

    def start(self) -> dict[str, Any]:
        """Start the daemon and return its identity."""

        state = start_daemon(self.project_root, self.forge_dir)
        return {
            "daemon_id": state.daemon_id,
            "pid": state.pid,
            "project_root": state.project_root,
            "started_at": state.started_at,
        }

    def stop(self) -> dict[str, Any]:
        """Stop the daemon; `stopped` is False when none was running."""

        return {"stopped": stop_daemon(self.forge_dir)}

    def status(self) -> dict[str, Any]:
        """Return the daemon status snapshot (liveness via pid probe)."""

        return daemon_status(self.forge_dir)

    def logs(self, limit: int = 50) -> list[str]:
        """Return the last `limit` lines of daemon.log; [] when missing."""

        log_path = DaemonStateStore(self.forge_dir).log_path
        if limit <= 0 or not log_path.exists():
            return []
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-limit:]

    def restart(self) -> dict[str, Any]:
        """Stop any running daemon, then start a fresh one."""

        _ = self.stop()
        return self.start()
