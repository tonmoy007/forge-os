"""Tests for the local JSONL span sink (FR-OBS-001 — S2)."""

from __future__ import annotations

from pathlib import Path

from forge_os.schemas.tracing import Span, SpanKind, SpanStatus
from forge_os.tracing.sink import SpanSink


def _span(span_id: str, trace_id: str = "trace-1", start: str = "2026-07-01T00:00:00Z") -> Span:
    return Span(
        trace_id=trace_id,
        span_id=span_id,
        name="AdapterSpawnStarted",
        kind=SpanKind.REASONING,
        start_time=start,
        status=SpanStatus.UNSET,
        attributes={"k": "v"},
    )


def test_write_creates_traces_dir_and_file(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path)

    sink.write([_span("a")])

    assert (tmp_path / "traces" / "spans.jsonl").exists()


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path)
    spans = [_span("a"), _span("b")]

    sink.write(spans)
    read = sink.read_all()

    assert [s.span_id for s in read] == ["a", "b"]
    assert read[0].attributes == {"k": "v"}
    assert read[0].kind is SpanKind.REASONING


def test_write_is_a_snapshot_not_an_append(tmp_path: Path) -> None:
    # Re-writing the full projection replaces the file — no duplication.
    sink = SpanSink(tmp_path)

    sink.write([_span("a"), _span("b")])
    sink.write([_span("a"), _span("b")])

    read = sink.read_all()
    assert [s.span_id for s in read] == ["a", "b"]


def test_write_empty_truncates(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path)
    sink.write([_span("a")])

    sink.write([])

    assert sink.read_all() == []
    assert (tmp_path / "traces" / "spans.jsonl").read_text(encoding="utf-8") == ""


def test_read_missing_file_returns_empty(tmp_path: Path) -> None:
    assert SpanSink(tmp_path).read_all() == []


def test_read_skips_malformed_lines(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path)
    sink.write([_span("a")])
    # Simulate a partially-written / corrupt trailing line.
    with open(sink.path, "a", encoding="utf-8") as handle:
        handle.write("{not json\n")
        handle.write('{"trace_id": "t", "missing": "required fields"}\n')

    read = sink.read_all()

    assert [s.span_id for s in read] == ["a"]


def test_write_leaves_no_temp_file(tmp_path: Path) -> None:
    sink = SpanSink(tmp_path)
    sink.write([_span("a")])

    leftovers = list((tmp_path / "traces").glob(".spans.jsonl.tmp-*"))
    assert leftovers == []


def test_read_preserves_extra_attributes(tmp_path: Path) -> None:
    # Span uses extra="allow"; unknown top-level fields must survive a round-trip.
    sink = SpanSink(tmp_path)
    span = _span("a")
    span_with_extra = span.model_copy(update={"resource": "svc"})
    sink.write([span_with_extra])

    read = sink.read_all()

    assert read[0].model_dump()["resource"] == "svc"
