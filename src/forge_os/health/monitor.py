"""Always-on health monitor — the daemon's periodic checker sweep (S6).

Runs the always-on monitor checkers (hook latency, token budget, cost cap) on a
daemon interval and raises a ``DaemonAlert`` for each unhealthy result, so a
degraded subsystem surfaces in `forge status` without anyone running
`forge health check` by hand. Alert-only per SRS v4.1 — it never disables
anything; the S5 cost self-throttle is the only component that *acts* on a signal.

Gated off by default (``features.health_monitor``); the daemon schedules this
only when a project opts in (see ``daemon/tasks.py::_health_monitor_tasks``).
These checkers are read-only *monitors*, so they are deliberately NOT wrapped in
the cost self-throttle — throttling the component that detects an overage would
be self-defeating (see ``daemon/throttle.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from forge_os.core.state_manager import utc_now
from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.health.cost_cap import CostCapHealthChecker
from forge_os.health.hook_latency import HookLatencyHealthChecker
from forge_os.health.token_budget import TokenBudgetHealthChecker
from forge_os.schemas.daemon import DaemonAlert

log = logging.getLogger("forge.health.monitor")


def _default_checkers(project_root: Path) -> dict[str, HealthChecker]:
    # The always-on monitor subset (scope §#4: budget / latency / cost-cap), NOT
    # the full run_full_check set — project-structure checks (state/gates/adg/...)
    # are not the daemon monitor's concern.
    return {
        "hook_latency": HookLatencyHealthChecker(project_root),
        "token_budget": TokenBudgetHealthChecker(project_root),
        "cost_cap": CostCapHealthChecker(project_root),
    }


class HealthMonitor:
    """Run the always-on checkers once per sweep and alert on unhealthy results.

    Dependencies are injectable for deterministic tests: ``now`` (RFC 3339 string
    clock) and ``checkers`` (name → ``HealthChecker``).
    """

    def __init__(
        self,
        project_root: Path,
        forge_dir: Path | None = None,
        *,
        now: Callable[[], str] | None = None,
        checkers: dict[str, HealthChecker] | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self._store = DaemonStateStore(forge_dir)
        self._now = now or utc_now
        self._checkers = checkers if checkers is not None else _default_checkers(self.project_root)

    def check(self) -> dict[str, Any]:
        """Run every checker once; alert on each unhealthy result.

        Per-checker crash isolation mirrors ``run_full_check``: one checker that
        raises must not abort the sweep or the scheduled task.
        """

        checked = unhealthy = alerted = 0
        for name, checker in self._checkers.items():
            try:
                result = checker.check()
            except Exception as exc:  # one bad checker must not kill the sweep
                log.warning("health checker %s crashed: %s", name, exc)
                continue
            checked += 1
            if result.healthy:
                continue
            unhealthy += 1
            if self._alert(name, result):
                alerted += 1
        return {"checked": checked, "unhealthy": unhealthy, "alerted": alerted}

    def _alert(self, name: str, result: HealthResult) -> bool:
        """Record a daemon alert for an unhealthy checker; best-effort.

        Mirrors ``ObserverMonitor._alert``: a missing/corrupt state store must not
        turn a health sweep into a task failure. ``add_alert`` de-dups consecutive
        identical alerts, so a persistently-unhealthy checker with a stable message
        does not flood the capped list.
        """

        severity: Literal["warning"] = "warning"  # alert-only per v4.1
        alert = DaemonAlert(
            alert_id=str(uuid4()),
            created_at=self._now(),
            source=f"health-{name}",
            severity=severity,
            message=result.message,
            metadata={"checker": name, "recommendations": result.recommendations},
        )
        try:
            _ = self._store.add_alert(alert)
        except DaemonStateError as exc:
            log.warning("dropped health alert from %s: %s", name, exc)
            return False
        return True
