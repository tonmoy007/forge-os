"""Tests for the neutral tracing Span model (OTLP tracing S1)."""

from __future__ import annotations

from forge_os.schemas.tracing import Span, SpanKind, SpanStatus


def _span(**overrides: object) -> Span:
    base: dict[str, object] = {
        "trace_id": "run-1",
        "span_id": "s1",
        "name": "spawn",
        "kind": SpanKind.REASONING,
        "start_time": "2026-07-01T00:00:00Z",
    }
    base.update(overrides)
    return Span(**base)


class TestSpan:
    def test_required_fields_and_defaults(self) -> None:
        span = _span()
        assert span.trace_id == "run-1"
        assert span.span_id == "s1"
        assert span.parent_span_id is None
        assert span.end_time is None
        assert span.status is SpanStatus.UNSET
        assert span.attributes == {}

    def test_kind_and_status_enum_values(self) -> None:
        assert SpanKind.REASONING == "reasoning"
        assert SpanKind.AUDIT == "audit"
        assert set(SpanStatus) == {SpanStatus.UNSET, SpanStatus.OK, SpanStatus.ERROR}
        assert SpanStatus.OK == "ok"

    def test_round_trips_through_dump_and_validate(self) -> None:
        span = _span(
            parent_span_id="root",
            end_time="2026-07-01T00:00:01Z",
            status=SpanStatus.OK,
            attributes={"run_id": "run-1", "adapter": "claude_code"},
        )
        restored = Span.model_validate(span.model_dump(mode="json"))
        assert restored == span

    def test_extra_fields_allowed(self) -> None:
        # extra="allow" keeps the model forward-compatible with new span fields.
        span = _span(vendor_field="x")
        assert span.model_dump()["vendor_field"] == "x"
