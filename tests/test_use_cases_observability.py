"""Tests for ObservabilityUseCases — `forge trace` (FR-SEM-002, FR-OBS-001 — S3)."""

from __future__ import annotations

import json
from pathlib import Path

from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project
from forge_os.schemas.tracing import Span, SpanKind, SpanStatus
from forge_os.use_cases.observability import ObservabilityUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Obs", profile="minimal")
    return tmp_path


class _FakeTracer:
    """Injectable tracer returning hand-built spans for deterministic tests."""

    def __init__(self, spans: list[Span]) -> None:
        self._spans = spans

    def collect(self) -> list[Span]:
        return list(self._spans)


def _span(trace_id: str, start: str, status: SpanStatus = SpanStatus.OK) -> Span:
    return Span(
        trace_id=trace_id,
        span_id=f"{trace_id}-1",
        name="span",
        kind=SpanKind.REASONING,
        start_time=start,
        status=status,
    )


def _seed_event(root: Path, run_id: str, event_type: str, payload: dict) -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(run_id, event_type, payload)
    store.close()


def _seed_audit(
    root: Path, audit_id: str, decision: str = "allowed", action: str = "shell"
) -> None:
    entry = {
        "audit_id": audit_id,
        "timestamp": "2026-07-01T10:00:00",
        "action": action,
        "decision": decision,
        "capability": "shell",
    }
    with open(root / ".forge" / "security-audit.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def test_get_trace_returns_ordered_spans_and_rollup(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {"stage": "srs"})
    _seed_event(root, "run-1", "AdapterSpawnCompleted", {"metadata": {"total_cost_usd": 0.02}})

    detail = ObservabilityUseCases(root).get_trace("run-1")

    assert detail.found is True
    assert detail.span_count == 2
    assert detail.kinds == ["reasoning"]
    assert detail.status == "ok"  # Completed → ok dominates the unset Started
    assert [s.name for s in detail.spans] == ["AdapterSpawnStarted", "AdapterSpawnCompleted"]
    assert detail.spans[0].attributes == {"stage": "srs"}


def test_get_trace_error_rollup(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    _seed_event(root, "run-1", "AdapterSpawnFailed", {"error": "boom"})

    detail = ObservabilityUseCases(root).get_trace("run-1")

    assert detail.status == "error"  # any errored span makes the trace error


def test_get_trace_unknown_id_is_not_found(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})

    detail = ObservabilityUseCases(root).get_trace("nope")

    assert detail.found is False
    assert detail.span_count == 0
    assert detail.spans == []


def test_audit_trace_is_standalone(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_audit(root, "aud-1", decision="denied")

    detail = ObservabilityUseCases(root).get_trace("aud-1")

    assert detail.found is True
    assert detail.kinds == ["audit"]
    assert detail.status == "error"  # denied → error
    assert detail.spans[0].attributes["capability"] == "shell"


def test_list_traces_summarizes_both_streams_sorted(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    _seed_event(root, "run-1", "AdapterSpawnCompleted", {})
    _seed_audit(root, "aud-1")

    report = ObservabilityUseCases(root).list_traces()

    ids = [t.trace_id for t in report.traces]
    assert set(ids) == {"run-1", "aud-1"}
    run_summary = next(t for t in report.traces if t.trace_id == "run-1")
    assert run_summary.span_count == 2
    assert run_summary.root_name == "AdapterSpawnStarted"
    assert run_summary.kinds == ["reasoning"]


def test_list_traces_empty_project(tmp_path: Path) -> None:
    root = _project(tmp_path)

    assert ObservabilityUseCases(root).list_traces().traces == []


def test_list_orders_chronologically_not_lexicographically(tmp_path: Path) -> None:
    # Two traces whose RAW timestamp strings sort OPPOSITE to their true instants,
    # using explicit offsets so the expectation is tz-independent (Docker runs UTC):
    #   x: 2026-07-01T23:00:00+00:00 -> instant 23:00Z (later)
    #   y: 2026-07-02T00:00:00+05:00 -> instant 19:00Z (earlier)
    # Lexicographic: "…01T23…" < "…02T00…" -> [x, y]. Chronological -> [y, x].
    tracer = _FakeTracer(
        [_span("x", "2026-07-01T23:00:00+00:00"), _span("y", "2026-07-02T00:00:00+05:00")]
    )
    report = ObservabilityUseCases(tmp_path, tracer=tracer).list_traces()

    assert [t.trace_id for t in report.traces] == ["y", "x"]


def test_unparseable_timestamp_sorts_last_without_crashing(tmp_path: Path) -> None:
    tracer = _FakeTracer(
        [_span("bad", "not-a-timestamp"), _span("good", "2026-07-01T10:00:00+00:00")]
    )
    report = ObservabilityUseCases(tmp_path, tracer=tracer).list_traces()

    assert [t.trace_id for t in report.traces] == ["good", "bad"]


def test_rollup_error_dominates_ok_in_same_trace(tmp_path: Path) -> None:
    # Both an OK and an ERROR span in ONE trace — the error must dominate, else a
    # failed spawn is hidden behind a sibling success (mutation-caught regression).
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnCompleted", {})  # ok
    _seed_event(root, "run-1", "AdapterSpawnFailed", {})  # error

    detail = ObservabilityUseCases(root).get_trace("run-1")

    assert detail.status == "error"


def test_reads_live_projection_not_the_sink(tmp_path: Path) -> None:
    # forge trace must work on a default (tracing-off) project: the sink is empty
    # but the source events exist, so the live projection still yields the trace.
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    assert (root / ".forge" / "traces" / "spans.jsonl").read_text(encoding="utf-8") == ""

    detail = ObservabilityUseCases(root).get_trace("run-1")

    assert detail.found is True
