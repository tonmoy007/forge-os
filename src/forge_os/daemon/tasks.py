"""Built-in daemon scheduled tasks (P10.02).

Later workstreams (Dreamer, Observer/ACP) register their background tasks here
by appending to the list returned from `build_scheduled_tasks`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.core.state_manager import utc_now
from forge_os.daemon.scheduler import ScheduledTask
from forge_os.daemon.state import DaemonStateError, DaemonStateStore

HEARTBEAT_INTERVAL_SECONDS = 30.0


def build_scheduled_tasks(
    project_root: Path, forge_dir: Path | None = None
) -> list[ScheduledTask]:
    """Return the built-in scheduled tasks for a daemon serving `project_root`."""

    _ = project_root  # reserved for project-scoped tasks added by later workstreams
    store = DaemonStateStore(forge_dir)

    def heartbeat() -> dict[str, Any] | None:
        state = store.load()
        if state is None:
            # Surfaced via TaskRunner.on_error; the daemon keeps running.
            raise DaemonStateError(
                f"No daemon state at {store.state_path}; heartbeat cannot update it."
            )
        state.last_heartbeat = utc_now()
        store.save(state)
        return {"last_heartbeat": state.last_heartbeat}

    return [
        ScheduledTask(
            name="heartbeat",
            interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            run=heartbeat,
        )
    ]
