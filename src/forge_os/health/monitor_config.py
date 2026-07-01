"""Always-on daemon monitor configuration (FR-HD-003/005, FR-COST-004).

Reads ``features.health_monitor`` from `.forge/config.yaml` defensively (the
``features`` mapping is an unvalidated ``dict[str, Any]``), mirroring
``context/token_monitor.resolve_warn_ratio``. Every malformed shape falls back to
a safe default: the monitor is off and uncapped unless explicitly configured.
This is the config seam the cost-cap checker reads now and the daemon task
(self-throttle / enable) will read later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge_os.config.loader import ConfigError, load_config
from forge_os.schemas.config import ConfigError as SchemaConfigError


@dataclass(frozen=True)
class HealthMonitorConfig:
    """Resolved always-on monitor settings."""

    enabled: bool = False
    # Absolute always-on $ cap (FR-COST-004). The SRS phrases it as "5% of the
    # project's average monthly production budget", but no production-budget field
    # exists, so the cap is an absolute configured value. None ⇒ uncapped.
    cost_cap_usd: float | None = None


def _positive_float(value: Any) -> float | None:
    # bool is an int subclass — reject it before the numeric check.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number > 0.0 else None


def load_health_monitor_config(features: dict[str, Any]) -> HealthMonitorConfig:
    """Resolve ``features.health_monitor`` to a config; never raises."""

    section = features.get("health_monitor")
    # Accept a bare `health_monitor: true` (enable with defaults), mirroring the
    # observer loader — otherwise a user who writes `true` gets silently disabled.
    if section is True:
        return HealthMonitorConfig(enabled=True)
    if not isinstance(section, dict):
        return HealthMonitorConfig()
    enabled = section.get("enabled", False)
    return HealthMonitorConfig(
        enabled=enabled if isinstance(enabled, bool) else False,
        cost_cap_usd=_positive_float(section.get("cost_cap_usd")),
    )


def load_health_monitor_config_from_project(project_root: Path) -> HealthMonitorConfig:
    """Resolve the full monitor config from a project's `.forge/config.yaml`.

    Mirrors ``load_observer_config``: a missing or broken config (either
    ``ConfigError`` class) resolves to the default (disabled), so the daemon
    monitor stays off and the daemon keeps running. This is the seam
    ``_health_monitor_tasks`` reads for its enable gate.
    """

    try:
        config = load_config(project_root / ".forge" / "config.yaml")
    except (ConfigError, SchemaConfigError):
        return HealthMonitorConfig()
    return load_health_monitor_config(config.features)


def resolve_cost_cap_usd(project_root: Path) -> float | None:
    """Resolve the configured always-on cost cap for a project, or None.

    Reads `features.health_monitor.cost_cap_usd` from `.forge/config.yaml`. A
    broken/missing config resolves to None (uncapped), so a malformed file never
    makes the cost-cap machinery flag or throttle spuriously. Shared by the
    cost-cap health checker and the daemon self-throttle.
    """

    return load_health_monitor_config_from_project(project_root).cost_cap_usd
