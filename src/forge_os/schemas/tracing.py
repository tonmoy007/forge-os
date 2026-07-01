"""Neutral tracing span model (FR-OBS-001, FR-SEM-002) — OTLP-mappable.

A provider-neutral span shared by both trace streams: reasoning spans (derived
from Event Store adapter events, correlated by run_id = the event ``stream_id``)
and runtime-audit spans (derived from ``security-audit.jsonl``, keyed by
``audit_id``). Kept deliberately generic so the later OTLP exporter can map it
onto OpenTelemetry without this model depending on any tracing SDK — ``schemas/``
holds pure Pydantic with zero forge_os imports.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpanKind(StrEnum):
    """Which of the two FR-OBS-001 streams a span belongs to."""

    REASONING = "reasoning"  # LLM / tool / MCP activity (Event Store events)
    AUDIT = "audit"  # runtime security-audit entries


class SpanStatus(StrEnum):
    """Neutral span outcome (mapped onto OTLP status codes by the exporter)."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class Span(BaseModel):
    """A single provider-neutral trace span.

    ``trace_id`` is the correlation key the index groups on: reasoning spans from
    one run share the run_id as their trace_id; audit entries use their audit_id.
    There is no shared session_id across the two streams, so cross-stream linkage
    is intentionally not asserted here (scope §#2c) — the index groups what the
    sources actually carry and does not fabricate a link.
    """

    model_config = ConfigDict(extra="allow")

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: SpanKind
    start_time: str  # RFC 3339
    end_time: str | None = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = Field(default_factory=dict)
