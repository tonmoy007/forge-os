"""Phase 10 daemon state schemas (P10.01)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DaemonTaskState(BaseModel):
    """Per-task run bookkeeping for a scheduled daemon task."""

    model_config = ConfigDict(extra="allow")

    last_run_at: str | None = None
    last_status: Literal["ok", "error"] | None = None
    runs: int = 0
    failures: int = 0
    last_error: str | None = None


class DaemonAlert(BaseModel):
    """A single alert raised by a daemon task or observer."""

    model_config = ConfigDict(extra="allow")

    alert_id: str
    created_at: str
    source: str
    severity: Literal["info", "warning", "critical"]
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DaemonState(BaseModel):
    """Canonical persisted state of a running (or last-run) Forge daemon."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    daemon_id: str
    pid: int
    project_root: str
    started_at: str
    last_heartbeat: str | None = None
    tasks: dict[str, DaemonTaskState] = Field(default_factory=dict)
    alerts: list[DaemonAlert] = Field(default_factory=list)
