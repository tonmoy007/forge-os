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
    if not isinstance(section, dict):
        return HealthMonitorConfig()
    enabled = section.get("enabled", False)
    return HealthMonitorConfig(
        enabled=enabled if isinstance(enabled, bool) else False,
        cost_cap_usd=_positive_float(section.get("cost_cap_usd")),
    )


def resolve_cost_cap_usd(project_root: Path) -> float | None:
    """Resolve the configured always-on cost cap for a project, or None.

    Loads `.forge/config.yaml` and reads `features.health_monitor.cost_cap_usd`.
    A broken config — either the loader's `ConfigError` or the schema's separate
    `ConfigError` (which pydantic does not wrap) — resolves to None (uncapped),
    so a malformed file never makes the cost-cap machinery flag or throttle
    spuriously. Shared by the cost-cap health checker and the daemon self-throttle.
    """

    try:
        config = load_config(project_root / ".forge" / "config.yaml")
    except (ConfigError, SchemaConfigError):
        return None
    return load_health_monitor_config(config.features).cost_cap_usd
