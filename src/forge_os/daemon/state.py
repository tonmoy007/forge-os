"""Persistent daemon state store under `<forge_dir>/daemon/` (P10.01)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from forge_os.core.state_manager import utc_now
from forge_os.schemas.daemon import DaemonAlert, DaemonState, DaemonTaskState

MAX_ALERTS = 100


class DaemonStateError(RuntimeError):
    """Raised when daemon state cannot be loaded, validated, or persisted."""


class DaemonStateStore:
    """Atomic load/save of `DaemonState` under `<forge_dir>/daemon/`.

    Follows L001/L005: `forge_dir` defaults to `~/.forge`; tests pass `tmp_path`.
    """

    def __init__(self, forge_dir: Path | None = None) -> None:
        self.forge_dir: Path = forge_dir or Path.home() / ".forge"
        self.daemon_dir: Path = self.forge_dir / "daemon"
        self.state_path: Path = self.daemon_dir / "state.json"
        self.log_path: Path = self.daemon_dir / "daemon.log"

    def load(self) -> DaemonState | None:
        """Return the persisted daemon state, or None when no state file exists."""

        if not self.state_path.exists():
            return None
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return DaemonState.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise DaemonStateError(f"Corrupt daemon state file: {self.state_path}") from exc
        except OSError as exc:
            raise DaemonStateError(f"Failed to read daemon state file: {self.state_path}") from exc

    def save(self, state: DaemonState) -> None:
        """Persist `state` atomically (tempfile + replace), creating parent dirs."""

        self.daemon_dir.mkdir(parents=True, exist_ok=True)
        content = json.dumps(state.model_dump(), indent=2) + "\n"
        temp_path = self.state_path.with_name(f".{self.state_path.name}.tmp-{uuid4()}")
        try:
            _ = temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, self.state_path)
        except OSError as exc:
            if temp_path.exists():
                temp_path.unlink()
            raise DaemonStateError(f"Failed to atomically write {self.state_path}") from exc

    def clear(self) -> None:
        """Remove the persisted state file if present."""

        self.state_path.unlink(missing_ok=True)

    def add_alert(self, alert: DaemonAlert) -> DaemonState:
        """Append `alert`, keeping only the most recent `MAX_ALERTS` entries."""

        state = self._load_required("add an alert")
        state.alerts = [*state.alerts, alert][-MAX_ALERTS:]
        self.save(state)
        return state

    def record_task_run(self, name: str, *, status: str, error: str | None = None) -> None:
        """Update run counters for task `name` after a scheduler run."""

        state = self._load_required(f"record a run of task `{name}`")
        task = state.tasks.get(name) or DaemonTaskState()
        task.last_run_at = utc_now()
        task.last_status = status  # type: ignore[assignment]
        task.runs += 1
        if status == "error":
            task.failures += 1
            task.last_error = error
        state.tasks[name] = task
        self.save(state)

    def _load_required(self, action: str) -> DaemonState:
        state = self.load()
        if state is None:
            raise DaemonStateError(
                f"No daemon state at {self.state_path}; cannot {action}. Is the daemon running?"
            )
        return state
