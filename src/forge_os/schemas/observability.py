"""Schemas for `forge trace` — read-only trace/span views (FR-SEM-002, FR-OBS-001).

Presentation models for the `forge trace` command: a neutral `Span` (schemas/
tracing.py) rendered for a human, plus per-trace summaries. Pure pydantic — no
forge_os imports. Enum-typed span fields are carried as their string values so
this stays a flat, JSON-friendly view model.
"""

from typing import Any

from pydantic import BaseModel, Field


class SpanView(BaseModel):
    """One span, flattened for display/JSON (kind/status as string values)."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: str
    start_time: str
    end_time: str | None = None
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceSummary(BaseModel):
    """One line per trace for the `forge trace` list view."""

    trace_id: str
    root_name: str  # name of the earliest span — a readable label for the trace
    span_count: int
    kinds: list[str]  # sorted unique span kinds in the trace (reasoning/audit)
    start_time: str  # earliest span start
    status: str  # rollup: error if any span errored, else ok if any ok, else unset


class TraceListReport(BaseModel):
    """All traces currently projected from the two sources."""

    traces: list[TraceSummary] = Field(default_factory=list)


class TraceDetail(BaseModel):
    """A single trace's spans plus its rollup, for `forge trace <trace_id>`."""

    trace_id: str
    found: bool  # False ⇒ no spans carry this trace_id
    span_count: int = 0
    kinds: list[str] = Field(default_factory=list)
    status: str = "unset"
    spans: list[SpanView] = Field(default_factory=list)
