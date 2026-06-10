"""Phase 10 observer schemas (P10.10, P10.14)."""

from pydantic import BaseModel, ConfigDict, Field


class ObserverConfig(BaseModel):
    """Observer feature configuration, loaded from `features.observer` in config.yaml."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = False
    poll_interval_seconds: float = 60.0
    acp_session_cleanup_interval_seconds: float = 300.0
    metrics_interval_seconds: float = 300.0
    stale_session_max_age_seconds: float = 3600.0


class AgentMetrics(BaseModel):
    """Per-agent uptime/restart counters persisted by the observer."""

    model_config = ConfigDict(extra="allow")

    uptime_seconds: float = 0.0
    restarts: int = 0
    last_check: str | None = None


class ObserverMetrics(BaseModel):
    """Observer metrics snapshot persisted at `<forge_dir>/daemon/metrics.json`."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    collected_at: str | None = None
    agents: dict[str, AgentMetrics] = Field(default_factory=dict)
