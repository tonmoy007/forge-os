"""Built-in daemon scheduled tasks (P10.02, P10.10-14).

Later workstreams register their background tasks here by appending to the
list returned from `build_scheduled_tasks`. Observer tasks are gated on the
`features.observer` flag in `.forge/config.yaml` and are absent by default.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from forge_os.core.state_manager import utc_now
from forge_os.daemon.scheduler import ScheduledTask
from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.daemon.throttle import CostThrottle, TaskRun, throttle_gate

log = logging.getLogger("forge.daemon.tasks")

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
    tasks.extend(_dreamer_tasks(project_root, forge_dir))
    tasks.extend(_observer_tasks(project_root, forge_dir))
    tasks.extend(_health_monitor_tasks(project_root, forge_dir))
    tasks.extend(_tracing_export_tasks(project_root))
    return tasks


# FR-BD-003: the daemon runs the Dream cycle on a schedule. Fixed-delay
# intervals (see TaskRunner semantics): daily digest/decay, weekly re-ingestion.
DREAMER_DAILY_INTERVAL_SECONDS = 86_400.0
DREAMER_WEEKLY_INTERVAL_SECONDS = 604_800.0


def _dreamer_tasks(project_root: Path, forge_dir: Path | None) -> list[ScheduledTask]:
    """Dreamer maintenance tasks (P10.05-09) — propose-only, never destructive.

    These are the daemon's cost-incurring maintenance surface (LLM consolidation),
    so each run is wrapped in the always-on cost self-throttle (FR-COST-004): when
    recorded spend approaches the configured cap the task skips and alerts instead
    of spending more. Uncapped ⇒ the gate is a pass-through and the task runs
    exactly as before.
    """

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

    throttle = CostThrottle(project_root)
    store = DaemonStateStore(forge_dir)

    def gated(name: str, run: TaskRun) -> TaskRun:
        return throttle_gate(run, throttle=throttle, store=store, task_name=name)

    specs: list[tuple[str, float, TaskRun]] = [
        ("dreamer-digest", DREAMER_DAILY_INTERVAL_SECONDS, digest),
        ("dreamer-decay", DREAMER_DAILY_INTERVAL_SECONDS, decay),
        ("dreamer-reingest", DREAMER_WEEKLY_INTERVAL_SECONDS, reingest),
    ]
    return [ScheduledTask(name, interval, gated(name, run)) for name, interval, run in specs]


# FR-HD-003/005, FR-COST-004: the always-on monitor sweeps the checkers on a
# schedule. Hourly — latency/budget/cost don't change second-to-second, and this
# bounds the alert rate against the capped DaemonState.alerts list.
HEALTH_MONITOR_INTERVAL_SECONDS = 3600.0


def _health_monitor_tasks(project_root: Path, forge_dir: Path | None) -> list[ScheduledTask]:
    """Return the health-monitor sweep when `features.health_monitor` enables it; else []."""

    # Lazy import: health.monitor imports daemon.state, and this module is imported
    # by the daemon package __init__ — a top-level import would create a circular
    # import (same reason _observer_tasks imports observer.monitor lazily).
    from forge_os.health.monitor import HealthMonitor
    from forge_os.health.monitor_config import load_health_monitor_config_from_project

    if not load_health_monitor_config_from_project(project_root).enabled:
        return []
    monitor = HealthMonitor(project_root, forge_dir)
    return [
        ScheduledTask(
            name="health-monitor",
            interval_seconds=HEALTH_MONITOR_INTERVAL_SECONDS,
            run=monitor.check,
        )
    ]


# FR-OBS-001: the daemon ships the local span projection to a configured OTLP
# collector. Five-minute cadence — export is I/O to a user collector, not
# latency-critical, and this bounds request volume.
TRACING_EXPORT_INTERVAL_SECONDS = 300.0


def _tracing_export_tasks(project_root: Path) -> list[ScheduledTask]:
    """Return the OTLP export task when tracing is enabled AND an endpoint is set.

    Gated three ways: `features.tracing.enabled` is on, `otlp_endpoint` is
    configured, and the optional `[tracing]` extra is installed. Configured but
    without the extra ⇒ log once and stay inert (never a silent no-op, never a
    crash). Default off, so an ordinary project schedules no export task.
    """

    from forge_os.tracing.config import load_tracing_config_from_project

    config = load_tracing_config_from_project(project_root)
    if not (config.enabled and config.otlp_endpoint):
        return []

    from forge_os.tracing.otlp import otlp_available

    if not otlp_available():
        log.warning(
            "tracing.otlp_endpoint is set but OTLP export is disabled: the "
            "optional `[tracing]` extra is not installed (pip install "
            "'forge-os[tracing]')."
        )
        return []

    endpoint = config.otlp_endpoint

    def export() -> dict[str, Any] | None:
        from forge_os.tracing.otlp import export_spans
        from forge_os.tracing.tracer import DualStreamTracer

        tracer = DualStreamTracer(project_root)
        spans = tracer.collect()
        tracer.emit()  # keep the local sink in sync with what was exported
        ok = export_spans(spans, endpoint)
        return {"exported": len(spans), "ok": ok}

    return [
        ScheduledTask(
            name="tracing-export",
            interval_seconds=TRACING_EXPORT_INTERVAL_SECONDS,
            run=export,
        )
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
