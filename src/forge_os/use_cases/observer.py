"""Observer use cases — status and one-shot health checks (P10.10-14)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.observer.monitor import ObserverMonitor
from forge_os.project.status import daemon_alerts


class ObserverUseCases:
    """Bridge between the CLI/integrator and the observer domain module."""

    def __init__(
        self,
        project_root: Path,
        forge_dir: Path | None = None,
        *,
        monitor: ObserverMonitor | None = None,
    ) -> None:
        self.project_root = project_root
        self.forge_dir = forge_dir
        self._monitor = monitor or ObserverMonitor(project_root, forge_dir)

    def status(self) -> dict[str, Any]:
        """Return observer config, the last metrics snapshot, and recent alerts."""

        metrics = self._monitor.load_metrics()
        return {
            "config": self._monitor.config.model_dump(),
            "metrics": metrics.model_dump() if metrics is not None else None,
            "alerts": daemon_alerts(self.forge_dir),
        }

    def run_checks(self) -> dict[str, Any]:
        """Run the registry, session-cleanup, and metrics checks once.

        Intended for manual invocation and testing; the daemon runs the same
        checks on its own schedule.
        """

        return {
            "registry": self._monitor.check_registry(),
            "sessions": self._monitor.cleanup_stale_sessions(),
            "metrics": self._monitor.collect_metrics(),
        }
