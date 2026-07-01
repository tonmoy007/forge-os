"""Always-on cost self-throttle for daemon maintenance (FR-COST-004).

When recorded spend approaches the configured cost cap, the daemon's
cost-incurring maintenance work throttles itself: the gated task skips its run
and records a single ``DaemonAlert`` instead of spending more. This is the
"daemon self-throttles when approaching cap" half of FR-COST-004 — S4 delivered
the alert-only cost-cap *health check*; this slice makes the daemon *act* on it.

Scope of the throttle (documented deviation, mirrors ``health/cost_cap.py``): the
target is the daemon's *cost-incurring* maintenance — the Dreamer tasks, the LLM
consolidation surface. Observer tasks (ACP restart/health/metrics) are
operational and must keep running when over budget; the health-monitor tasks
(S6) are the monitors that *detect* the overage. Throttling either would be
self-defeating, so only cost-incurring maintenance is gated. Skill Miner is a
persona, not a daemon task, so it is out of the cap set (scope §#4(d)).

Metering inherits S4's deviation: ``CostAggregator`` sums TOTAL recorded spend, so
the cap is a lifetime (not monthly) cap and the throttle is sticky until the cap
is raised. Monthly windowing awaits event-time filtering.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from forge_os.core.state_manager import utc_now
from forge_os.cost.aggregator import CostAggregator
from forge_os.daemon.state import DaemonStateError, DaemonStateStore
from forge_os.health.cost_cap import CAP_WARN_RATIO
from forge_os.health.monitor_config import resolve_cost_cap_usd
from forge_os.schemas.daemon import DaemonAlert

log = logging.getLogger("forge.daemon.throttle")

# The throttle trips at the same ratio the health checker calls "approaching",
# so "approaching the cap" in `forge health check` and "the daemon throttled"
# are one threshold, not two that can drift apart.
THROTTLE_RATIO = CAP_WARN_RATIO

TaskRun = Callable[[], dict[str, Any] | None]

_ALERT_SOURCE = "cost-throttle"
# Stable across runs so DaemonStateStore.add_alert's consecutive-duplicate
# suppression collapses a persistently-throttled task to a single alert; the
# per-run numbers live in the alert metadata instead of the message.
_ALERT_MESSAGE = "Always-on cost cap reached; throttling daemon maintenance."


@dataclass(frozen=True)
class ThrottleDecision:
    """Whether cost-incurring daemon maintenance should throttle right now."""

    throttled: bool
    spent_usd: float
    cost_cap_usd: float | None  # None ⇒ uncapped
    ratio: float | None  # None ⇒ uncapped (no ratio to report)


class CostThrottle:
    """Decide whether to throttle from recorded spend vs the configured cap.

    Stateless: each ``evaluate`` re-reads spend and the cap, so gated tasks act on
    the live figure, never a stale shared flag. ``cost_cap_usd`` may be injected
    for deterministic tests; None ⇒ resolve from ``.forge/config.yaml``.
    """

    def __init__(self, project_root: Path, *, cost_cap_usd: float | None = None) -> None:
        self.project_root = Path(project_root)
        # None ⇒ resolve from config; an explicit value is for deterministic tests.
        self._cost_cap_usd = cost_cap_usd

    def evaluate(self) -> ThrottleDecision:
        cap = self._cost_cap_usd
        if cap is None:
            cap = resolve_cost_cap_usd(self.project_root)
        spent = CostAggregator(self.project_root).totals().total_cost_usd or 0.0
        if cap is None or cap <= 0:
            # Uncapped ⇒ never throttle; the gate is a pass-through.
            return ThrottleDecision(throttled=False, spent_usd=spent, cost_cap_usd=cap, ratio=None)
        ratio = spent / cap
        return ThrottleDecision(
            throttled=ratio >= THROTTLE_RATIO,
            spent_usd=spent,
            cost_cap_usd=cap,
            ratio=ratio,
        )


def throttle_gate(
    run: TaskRun,
    *,
    throttle: CostThrottle,
    store: DaemonStateStore,
    task_name: str,
) -> TaskRun:
    """Wrap ``run`` so it self-throttles when spend approaches the cost cap.

    When throttled, the inner ``run`` is NOT invoked: the wrapper records one
    (deduped) ``DaemonAlert`` and returns a throttle summary. When clear, the
    inner run executes and its result passes through unchanged.
    """

    def gated() -> dict[str, Any] | None:
        decision = throttle.evaluate()
        if not decision.throttled:
            return run()
        _record_throttle_alert(store, task_name, decision)
        return {
            "throttled": True,
            "task": task_name,
            **_decision_metrics(decision),
        }

    return gated


def _decision_metrics(decision: ThrottleDecision) -> dict[str, Any]:
    return {
        "spent_usd": round(decision.spent_usd, 6),
        "cost_cap_usd": decision.cost_cap_usd,
        "ratio": round(decision.ratio, 3) if decision.ratio is not None else None,
    }


def _record_throttle_alert(
    store: DaemonStateStore, task_name: str, decision: ThrottleDecision
) -> bool:
    """Record a deduped throttle alert; best-effort (no daemon state ⇒ skip).

    Mirrors ``ObserverMonitor._alert``: a missing/corrupt state store must not
    turn a deliberate throttle into a task failure, and add_alert already caps
    and de-dups the list so a persistently-throttled task never floods it.
    """

    alert = DaemonAlert(
        alert_id=str(uuid4()),
        created_at=utc_now(),
        source=_ALERT_SOURCE,
        severity="warning",
        message=_ALERT_MESSAGE,
        metadata={"task": task_name, **_decision_metrics(decision)},
    )
    try:
        _ = store.add_alert(alert)
    except DaemonStateError as exc:
        log.warning("dropped cost-throttle alert for task %s: %s", task_name, exc)
        return False
    return True
