"""Tests for the TraceIndex correlation index (OTLP tracing S1)."""

from __future__ import annotations

from forge_os.schemas.tracing import Span, SpanKind
from forge_os.tracing import TraceIndex


def _span(
    trace_id: str, span_id: str, start_time: str, kind: SpanKind = SpanKind.REASONING
) -> Span:
    return Span(
        trace_id=trace_id,
        span_id=span_id,
        name=span_id,
        kind=kind,
        start_time=start_time,
    )


class TestTraceIndex:
    def test_empty(self) -> None:
        index = TraceIndex([])
        assert index.trace_ids() == []
        assert index.spans_for("nope") == []

    def test_groups_by_trace_id(self) -> None:
        spans = [
            _span("run-1", "a", "2026-07-01T00:00:00Z"),
            _span("run-1", "b", "2026-07-01T00:00:01Z"),
            _span("run-2", "c", "2026-07-01T00:00:02Z"),
        ]
        index = TraceIndex(spans)
        assert set(index.trace_ids()) == {"run-1", "run-2"}
        assert [s.span_id for s in index.spans_for("run-1")] == ["a", "b"]
        assert [s.span_id for s in index.spans_for("run-2")] == ["c"]

    def test_spans_are_time_ordered(self) -> None:
        # Inserted out of chronological order — must come back sorted by start_time.
        spans = [
            _span("run-1", "late", "2026-07-01T00:00:03Z"),
            _span("run-1", "early", "2026-07-01T00:00:01Z"),
            _span("run-1", "mid", "2026-07-01T00:00:02Z"),
        ]
        assert [s.span_id for s in TraceIndex(spans).spans_for("run-1")] == ["early", "mid", "late"]

    def test_equal_start_times_break_ties_by_span_id(self) -> None:
        spans = [
            _span("run-1", "z", "2026-07-01T00:00:00Z"),
            _span("run-1", "a", "2026-07-01T00:00:00Z"),
        ]
        assert [s.span_id for s in TraceIndex(spans).spans_for("run-1")] == ["a", "z"]

    def test_trace_ids_preserve_first_seen_order(self) -> None:
        # Documented contract (S3 forge trace renders in this order): trace_ids are
        # first-seen order, NOT sorted. Pin it so a `sorted(...)` refactor can't
        # silently break the ordering guarantee.
        spans = [
            _span("run-z", "s1", "2026-07-01T00:00:00Z"),
            _span("run-a", "s2", "2026-07-01T00:00:01Z"),
            _span("run-m", "s3", "2026-07-01T00:00:02Z"),
        ]
        assert TraceIndex(spans).trace_ids() == ["run-z", "run-a", "run-m"]

    def test_unknown_trace_id_returns_empty(self) -> None:
        index = TraceIndex([_span("run-1", "a", "2026-07-01T00:00:00Z")])
        assert index.spans_for("missing") == []

    def test_reasoning_and_audit_streams_stay_separate(self) -> None:
        # No shared session_id (scope §#2c): a multi-span reasoning trace and a
        # standalone audit span are distinct traces, not merged.
        spans = [
            _span("run-1", "r1", "2026-07-01T00:00:00Z", SpanKind.REASONING),
            _span("run-1", "r2", "2026-07-01T00:00:01Z", SpanKind.REASONING),
            _span("audit-9", "a1", "2026-07-01T00:00:02Z", SpanKind.AUDIT),
        ]
        index = TraceIndex(spans)
        assert set(index.trace_ids()) == {"run-1", "audit-9"}
        assert len(index.spans_for("run-1")) == 2
        assert [s.kind for s in index.spans_for("audit-9")] == [SpanKind.AUDIT]

    def test_spans_for_returns_a_copy(self) -> None:
        index = TraceIndex([_span("run-1", "a", "2026-07-01T00:00:00Z")])
        got = index.spans_for("run-1")
        got.clear()
        assert len(index.spans_for("run-1")) == 1  # index unaffected by caller mutation
