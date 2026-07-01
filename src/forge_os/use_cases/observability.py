"""Use case for `forge trace` — read a correlated trace of neutral spans.

Projects the two local sources (Event Store reasoning events + security-audit
entries) into neutral spans via ``DualStreamTracer``, groups them with
``TraceIndex``, and returns flat presentation models.

**Design note — reads the LIVE projection, not the sink.** `forge trace` is a
read-only diagnostic, so it must work regardless of the default-off
``features.tracing`` emission toggle. It therefore reads ``DualStreamTracer.collect()``
(a pure projection of the always-present sources) rather than the emitted
``.forge/traces/spans.jsonl`` sink — which stays empty until a project opts into
emission. The sink + ``emit`` remain the persistence/OTLP-export path (S4). This
is a deliberate deviation from the S2 RESUME note ("reads the sink"): reading the
sink would make `forge trace` show nothing on a default (tracing-off) project even
though the source events exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from forge_os.schemas.observability import (
    SpanView,
    TraceDetail,
    TraceListReport,
    TraceSummary,
)
from forge_os.schemas.tracing import Span, SpanStatus
from forge_os.tracing import DualStreamTracer, TraceIndex


def _span_view(span: Span) -> SpanView:
    return SpanView(
        trace_id=span.trace_id,
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        name=span.name,
        kind=span.kind.value,
        start_time=span.start_time,
        end_time=span.end_time,
        status=span.status.value,
        attributes=dict(span.attributes),
    )


def _kinds(spans: Sequence[Span]) -> list[str]:
    return sorted({span.kind.value for span in spans})


def _sort_instant(start_time: str) -> tuple[int, float]:
    """Chronological sort key across the two streams' timestamp formats.

    Reasoning spans carry UTC RFC 3339 (``…Z``, from the Event Store); audit spans
    carry naive local time (``datetime.now().isoformat()``, no offset). A raw-string
    sort mis-orders UTC vs local on a non-UTC host, so parse both to a real instant.
    Naive timestamps are treated as machine-local (a local-first tool writes and
    reads them on the same host). Unparseable timestamps sort last (flag ``1``).
    """

    try:
        parsed = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except ValueError:
        return (1, 0.0)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return (0, parsed.timestamp())


def _rollup_status(spans: Sequence[Span]) -> str:
    """A trace is ERROR if any span errored, else OK if any span is OK, else UNSET."""

    statuses = {span.status for span in spans}
    if SpanStatus.ERROR in statuses:
        return SpanStatus.ERROR.value
    if SpanStatus.OK in statuses:
        return SpanStatus.OK.value
    return SpanStatus.UNSET.value


def _summarize(trace_id: str, spans: Sequence[Span]) -> TraceSummary:
    # `spans` is time-ordered by TraceIndex, so spans[0] is the earliest.
    return TraceSummary(
        trace_id=trace_id,
        root_name=spans[0].name,
        span_count=len(spans),
        kinds=_kinds(spans),
        start_time=spans[0].start_time,
        status=_rollup_status(spans),
    )


class ObservabilityUseCases:
    """Read-only trace views for `forge trace`."""

    def __init__(self, project_root: Path, *, tracer: DualStreamTracer | None = None) -> None:
        self.project_root = Path(project_root)
        self._tracer = tracer

    def _index(self) -> TraceIndex:
        tracer = self._tracer or DualStreamTracer(self.project_root)
        return TraceIndex(tracer.collect())

    def list_traces(self) -> TraceListReport:
        """Summaries of every projected trace, ordered chronologically then by id."""

        index = self._index()
        summaries = [_summarize(tid, index.spans_for(tid)) for tid in index.trace_ids()]
        summaries.sort(key=lambda s: (*_sort_instant(s.start_time), s.trace_id))
        return TraceListReport(traces=summaries)

    def get_trace(self, trace_id: str) -> TraceDetail:
        """One trace's spans + rollup; ``found=False`` for an unknown trace_id."""

        spans = self._index().spans_for(trace_id)
        return TraceDetail(
            trace_id=trace_id,
            found=bool(spans),
            span_count=len(spans),
            kinds=_kinds(spans),
            status=_rollup_status(spans),
            spans=[_span_view(span) for span in spans],
        )
