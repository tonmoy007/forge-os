"""Phase 03 normalized lifecycle event model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "SessionStart",
    "UserPromptSubmit",
    "StageStarted",
    "StageCompleted",
    "StageBlocked",
    "StageOverride",
    "GateStarted",
    "GateCompleted",
    "Stop",
    "SubagentStop",
    "SessionEnd",
    "ArtifactChanged",
    "HookStarted",
    "HookCompleted",
    "HookFailed",
    "HookTimedOut",
    # Phase 08 event types
    "BacktrackTicketCreated",
    "BacktrackTicketApproved",
    "BacktrackReworkStarted",
    "BacktrackReworkCompleted",
    "SecurityActionAudited",
    "ACPRegistryDiscovered",
    "ACPAgentInstalled",
    "ACPSessionStarted",
    "ACPSessionClosed",
    "ExternalCommandGateEvaluated",
    "MetricThresholdGateEvaluated",
    # Event Store dual-write event types
    "StateSaved",
    # Observability event types
    "TokenBudgetExceeded",
]


def utc_now() -> str:
    """Return an RFC 3339 UTC timestamp."""

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class EventActor(BaseModel):
    """Actor attached to a lifecycle event."""

    model_config = ConfigDict(extra="allow")

    type: str
    id: str


class LifecycleEvent(BaseModel):
    """Normalized event record persisted to `.forge/events.jsonl`."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = "0.1"
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4()}")
    correlation_id: str | None = None
    event_type: EventType
    timestamp: str = Field(default_factory=utc_now)
    session_id: str | None = None
    stage_id: str | None = None
    actor: EventActor
    payload: dict[str, Any] = Field(default_factory=dict)
    redactions: list[str] = Field(default_factory=list)


def new_event(
    event_type: EventType,
    *,
    stage_id: str | None = None,
    session_id: str | None = None,
    correlation_id: str | None = None,
    actor_type: str = "core",
    actor_id: str = "forge-os",
    payload: dict[str, Any] | None = None,
) -> LifecycleEvent:
    """Build a normalized lifecycle event."""

    return LifecycleEvent(
        event_type=event_type,
        correlation_id=correlation_id,
        session_id=session_id,
        stage_id=stage_id,
        actor=EventActor(type=actor_type, id=actor_id),
        payload=payload or {},
    )
