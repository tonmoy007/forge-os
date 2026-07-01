"""Dual-stream tracing (FR-OBS-001, FR-SEM-002)."""

from forge_os.tracing.config import (
    TracingConfig,
    load_tracing_config,
    load_tracing_config_from_project,
)
from forge_os.tracing.index import TraceIndex
from forge_os.tracing.sink import SpanSink
from forge_os.tracing.tracer import (
    DualStreamTracer,
    audit_spans_from_entries,
    reasoning_spans_from_rows,
)

__all__ = [
    "DualStreamTracer",
    "SpanSink",
    "TraceIndex",
    "TracingConfig",
    "audit_spans_from_entries",
    "load_tracing_config",
    "load_tracing_config_from_project",
    "reasoning_spans_from_rows",
]
