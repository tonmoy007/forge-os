"""Dual-stream tracing configuration (FR-OBS-001, FR-SEM-002).

Reads ``features.tracing`` from `.forge/config.yaml` defensively (the ``features``
mapping is an unvalidated ``dict[str, Any]``), mirroring
``health/monitor_config.load_health_monitor_config``. Every malformed shape falls
back to a safe default: tracing is **off** unless explicitly enabled.

Deliberately does NOT add a ``TracingConfig`` field to ``schemas/config.py`` — that
is a canonical core schema, and the owner constraint is to never mutate the core
(scope §#2d). This consumer-side loader follows the ``observer``/``health_monitor``
precedent instead. ``otlp_endpoint`` is carried here for the S4 exporter; this
slice only uses ``enabled`` to gate local-sink emission.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge_os.config.loader import ConfigError, load_config
from forge_os.schemas.config import ConfigError as SchemaConfigError


@dataclass(frozen=True)
class TracingConfig:
    """Resolved tracing settings."""

    # Gates local-sink emission (``.forge/traces/spans.jsonl``). Default off.
    enabled: bool = False
    # OTLP collector endpoint (S4). None ⇒ local sink only, no OTLP export.
    otlp_endpoint: str | None = None


def _clean_endpoint(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def load_tracing_config(features: dict[str, Any]) -> TracingConfig:
    """Resolve ``features.tracing`` to a config; never raises.

    Accepts a bare ``tracing: true`` (enable with defaults) or a mapping with
    ``enabled`` / ``otlp_endpoint`` — otherwise a user who writes ``true`` gets
    silently disabled (the observer-loader footgun).
    """

    section = features.get("tracing")
    if section is True:
        return TracingConfig(enabled=True)
    if not isinstance(section, dict):
        return TracingConfig()
    enabled = section.get("enabled", False)
    return TracingConfig(
        enabled=enabled if isinstance(enabled, bool) else False,
        otlp_endpoint=_clean_endpoint(section.get("otlp_endpoint")),
    )


def load_tracing_config_from_project(project_root: Path) -> TracingConfig:
    """Resolve the tracing config from a project's `.forge/config.yaml`.

    Mirrors ``load_health_monitor_config_from_project``: a missing or broken
    config (either ``ConfigError`` class) resolves to the default (disabled), so
    tracing stays off and never breaks the caller.
    """

    try:
        config = load_config(project_root / ".forge" / "config.yaml")
    except (ConfigError, SchemaConfigError):
        return TracingConfig()
    return load_tracing_config(config.features)
