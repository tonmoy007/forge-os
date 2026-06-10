"""Built-in daemon scheduled tasks (P10.02, P10.10-14).

Later workstreams register their background tasks here by appending to the
list returned from `build_scheduled_tasks`. Observer tasks are gated on the
`features.observer` flag in `.forge/config.yaml` and are absent by default.
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

    tasks = [
        ScheduledTask(
            name="heartbeat",
            interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            run=heartbeat,
        )
    ]
    tasks.extend(_dreamer_tasks(project_root))
    tasks.extend(_observer_tasks(project_root, forge_dir))
    return tasks


# FR-BD-003: the daemon runs the Dream cycle on a schedule. Fixed-delay
# intervals (see TaskRunner semantics): daily digest/decay, weekly re-ingestion.
DREAMER_DAILY_INTERVAL_SECONDS = 86_400.0
DREAMER_WEEKLY_INTERVAL_SECONDS = 604_800.0


def _dreamer_tasks(project_root: Path) -> list[ScheduledTask]:
    """Dreamer maintenance tasks (P10.05-09) — propose-only, never destructive."""

    # Imported lazily for symmetry with _observer_tasks and to keep daemon
    # package import light when tasks are never built.
    from forge_os.dreamer.decay import apply_decay
    from forge_os.dreamer.digest import DailyDigestWriter
    from forge_os.dreamer.tensions import reingest_reflections
    from forge_os.memory.lessons import LessonStore

    def digest() -> dict[str, Any] | None:
        written = DailyDigestWriter(project_root).write()
        return {"written": written is not None, "path": str(written) if written else None}

    def decay() -> dict[str, Any] | None:
        return dict(apply_decay(LessonStore(project_root)))

    def reingest() -> dict[str, Any] | None:
        result = reingest_reflections(project_root)
        # Tension dicts are verbose; the run record only needs counts.
        return {
            "reflections_scanned": result["reflections_scanned"],
            "tensions": len(result["tensions"]),
            "lessons_proposed": len(result["lessons_proposed"]),
        }

    return [
        ScheduledTask("dreamer-digest", DREAMER_DAILY_INTERVAL_SECONDS, digest),
        ScheduledTask("dreamer-decay", DREAMER_DAILY_INTERVAL_SECONDS, decay),
        ScheduledTask("dreamer-reingest", DREAMER_WEEKLY_INTERVAL_SECONDS, reingest),
    ]


def _observer_tasks(project_root: Path, forge_dir: Path | None) -> list[ScheduledTask]:
    """Return observer tasks when `features.observer` enables them; else []."""

    # Imported lazily: observer.monitor imports daemon.state, and this module
    # is imported by the daemon package __init__ — a top-level import here
    # would create a circular import.
    from forge_os.observer.monitor import ObserverMonitor, load_observer_config

    config = load_observer_config(project_root)
    if not config.enabled:
        return []
    monitor = ObserverMonitor(project_root, forge_dir, config=config)
    return [
        ScheduledTask(
            name="observer-registry",
            interval_seconds=config.poll_interval_seconds,
            run=monitor.check_registry,
        ),
        ScheduledTask(
            name="observer-session-cleanup",
            interval_seconds=config.acp_session_cleanup_interval_seconds,
            run=monitor.cleanup_stale_sessions,
        ),
        ScheduledTask(
            name="observer-agent-health",
            interval_seconds=config.acp_agent_health_interval_seconds,
            run=monitor.restart_unhealthy_agents,
        ),
        ScheduledTask(
            name="observer-metrics",
            interval_seconds=config.metrics_interval_seconds,
            run=monitor.collect_metrics,
        ),
    ]
