"""Cost cap health checker (FR-COST-004).

Sums recorded $ spend (``CostAggregator``) and flags when it reaches a configurable
absolute cap (``features.health_monitor.cost_cap_usd``). Alert-only: it surfaces
"approaching"/"over" in `forge health check`; the daemon self-throttle is a later
slice. Uncapped (no cap configured) ⇒ healthy/inert, so existing projects are
unaffected until an owner opts in.

Two documented deviations from FR-COST-004's verbatim wording
(SCOPE-observability-cost-backlog.md §#4):
  - "5% of the project's average monthly production budget" is unimplementable —
    no production-budget field exists — so the cap is an absolute configured value.
  - The FR scopes the cap to the daemon components (Dreamer/Observer/Skill Miner/
    Health Daemon) "collectively", but spawn events carry no daemon-vs-production
    origin marker, and those components don't record cost-bearing spawns today. So
    the cap meters TOTAL recorded spend (reported as "Recorded spend", not
    "daemon spend"); daemon-scoped attribution awaits an origin marker on spawns.
"""

from __future__ import annotations

from pathlib import Path

from forge_os.config.loader import ConfigError, load_config
from forge_os.cost.aggregator import CostAggregator
from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.health.monitor_config import load_health_monitor_config
from forge_os.schemas.config import ConfigError as SchemaConfigError

# Alert as "approaching" once spend reaches this fraction of the cap (the
# self-throttle trigger the daemon will act on); "over" at/above the cap itself.
CAP_WARN_RATIO = 0.80


class CostCapHealthChecker(HealthChecker):
    """Flag always-on spend approaching/over the configured cost cap."""

    def __init__(self, project_root: Path, *, cost_cap_usd: float | None = None) -> None:
        self.project_root = Path(project_root)
        # None ⇒ resolve from config; an explicit value is for deterministic tests.
        self._cost_cap_usd = cost_cap_usd

    def check(self) -> HealthResult:
        cap = self._cost_cap_usd if self._cost_cap_usd is not None else self._resolve_cap()
        totals = CostAggregator(self.project_root).totals()
        spent = totals.total_cost_usd or 0.0
        details: dict[str, object] = {
            "cost_cap_usd": cap,
            "spent_usd": round(spent, 6),
            "priced_spawns": totals.priced_spawns,
            "total_spawns": totals.total_spawns,
        }

        if cap is None or cap <= 0:
            return HealthResult(
                healthy=True,
                message="No cost cap configured.",
                details=details,
            )

        ratio = spent / cap
        details["ratio"] = round(ratio, 3)
        if ratio >= 1.0:
            return HealthResult(
                healthy=False,
                message=f"Recorded spend ${spent:.2f} is over the ${cap:.2f} cost cap.",
                details=details,
                recommendations=["Reduce recorded activity or raise the configured cost cap."],
            )
        if ratio >= CAP_WARN_RATIO:
            return HealthResult(
                healthy=False,
                message=(
                    f"Recorded spend ${spent:.2f} is approaching "
                    f"the ${cap:.2f} cost cap ({ratio:.0%})."
                ),
                details=details,
                recommendations=["Reduce recorded activity or raise the configured cost cap."],
            )
        return HealthResult(
            healthy=True,
            message=f"Recorded spend ${spent:.2f} within the ${cap:.2f} cost cap ({ratio:.0%}).",
            details=details,
        )

    def _resolve_cap(self) -> float | None:
        # Mirror the S3 checker: load_config raises the loader's ConfigError or the
        # schema's (a separate class it does not wrap); a broken config ⇒ uncapped.
        try:
            config = load_config(self.project_root / ".forge" / "config.yaml")
        except (ConfigError, SchemaConfigError):
            return None
        return load_health_monitor_config(config.features).cost_cap_usd
