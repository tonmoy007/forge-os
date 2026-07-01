"""Tests for the DualStreamTracer + span builders (FR-OBS-001 — S2)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from forge_os.events.store import EventStore
from forge_os.project.scaffold import initialize_project
from forge_os.schemas.tracing import SpanKind, SpanStatus
from forge_os.tracing import TraceIndex
from forge_os.tracing.config import TracingConfig
from forge_os.tracing.sink import SpanSink
from forge_os.tracing.tracer import (
    DualStreamTracer,
    audit_spans_from_entries,
    reasoning_spans_from_rows,
)

# ── project / source seeding helpers ─────────────────────────────────────


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Trace", profile="minimal")
    return tmp_path


def _seed_event(root: Path, run_id: str, event_type: str, payload: dict) -> None:
    store = EventStore(root / ".forge" / "events.db")
    store.append(run_id, event_type, payload)
    store.close()


def _seed_audit(root: Path, entry: dict) -> None:
    path = root / ".forge" / "security-audit.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _audit_entry(audit_id: str, decision: str = "allowed", action: str = "execute_command") -> dict:
    return {
        "schema_version": "0.1.0",
        "audit_id": audit_id,
        "timestamp": "2026-07-01T10:00:00",
        "actor": {"type": "adapter", "id": "claude_code"},
        "action": action,
        "target": "ls -la",
        "capability": "shell",
        "decision": decision,
        "reason": None,
        "redactions": [],
    }


# ── reasoning_spans_from_rows ────────────────────────────────────────────


def test_reasoning_span_fields_map_from_row() -> None:
    rows = [
        {
            "event_id": 7,
            "stream_id": "run-1",
            "event_type": "AdapterStreamEvent",
            "payload": json.dumps({"text": "hi"}),
            "version": 1,
            "created_at": "2026-07-01T00:00:01Z",
        }
    ]

    spans = reasoning_spans_from_rows(rows)

    assert len(spans) == 1
    span = spans[0]
    assert span.trace_id == "run-1"  # stream_id (= run_id) is the trace key
    assert span.span_id == "7"  # event_id → stable span id
    assert span.name == "AdapterStreamEvent"
    assert span.kind is SpanKind.REASONING
    assert span.start_time == "2026-07-01T00:00:01Z"
    assert span.attributes == {"text": "hi"}


def test_reasoning_status_mapping() -> None:
    def status_for(event_type: str) -> SpanStatus:
        rows = [
            {
                "event_id": 1,
                "stream_id": "r",
                "event_type": event_type,
                "payload": "{}",
                "created_at": "2026-07-01T00:00:00Z",
            }
        ]
        return reasoning_spans_from_rows(rows)[0].status

    assert status_for("AdapterSpawnFailed") is SpanStatus.ERROR
    assert status_for("AdapterSpawnCompleted") is SpanStatus.OK
    assert status_for("AdapterSpawnStarted") is SpanStatus.UNSET


def test_reasoning_malformed_payload_yields_empty_attributes() -> None:
    rows = [
        {
            "event_id": 1,
            "stream_id": "r",
            "event_type": "AdapterStreamEvent",
            "payload": "{not json",
            "created_at": "2026-07-01T00:00:00Z",
        }
    ]

    spans = reasoning_spans_from_rows(rows)

    # The event still happened — keep the span, drop only the unparseable attrs.
    assert len(spans) == 1
    assert spans[0].attributes == {}


def test_reasoning_skips_structurally_unusable_rows() -> None:
    rows = [
        {"event_id": 1, "event_type": "X", "created_at": "t"},  # no stream_id
        {"stream_id": "r", "event_type": "X", "created_at": "t"},  # no event_id
        {"event_id": 2, "stream_id": "r", "created_at": "t"},  # no event_type
        {"event_id": 3, "stream_id": "r", "event_type": "X"},  # no created_at
        {"event_id": 4, "stream_id": "", "event_type": "X", "created_at": "t"},  # blank id
    ]

    assert reasoning_spans_from_rows(rows) == []


# ── audit_spans_from_entries ─────────────────────────────────────────────


def test_audit_span_fields_map_from_entry() -> None:
    spans = audit_spans_from_entries([_audit_entry("aud-1", decision="denied")])

    assert len(spans) == 1
    span = spans[0]
    assert span.trace_id == "aud-1"  # each audit entry is its own standalone trace
    assert span.span_id == "aud-1"
    assert span.name == "execute_command"
    assert span.kind is SpanKind.AUDIT
    assert span.start_time == "2026-07-01T10:00:00"
    assert span.status is SpanStatus.ERROR  # denied → error
    # audit_id / timestamp are promoted to structural fields, not duplicated.
    assert "audit_id" not in span.attributes
    assert "timestamp" not in span.attributes
    assert span.attributes["capability"] == "shell"


def test_audit_status_mapping() -> None:
    def status_for(decision: str) -> SpanStatus:
        return audit_spans_from_entries([_audit_entry("a", decision=decision)])[0].status

    assert status_for("denied") is SpanStatus.ERROR
    assert status_for("failed") is SpanStatus.ERROR
    assert status_for("allowed") is SpanStatus.OK
    assert status_for("warned") is SpanStatus.OK
    assert status_for("something-else") is SpanStatus.UNSET


def test_audit_non_scalar_decision_maps_to_unset_without_crashing() -> None:
    # A corrupt/foreign audit entry whose `decision` is a list/dict is unhashable;
    # the status membership test must not raise TypeError — it degrades to UNSET
    # and still builds the span (tolerance guarantee).
    for bad_decision in ({"v": "denied"}, ["denied"]):
        entry = _audit_entry("a")
        entry["decision"] = bad_decision
        spans = audit_spans_from_entries([entry])
        assert len(spans) == 1
        assert spans[0].status is SpanStatus.UNSET


def test_audit_skips_entries_missing_keys_or_wrong_type() -> None:
    entries = [
        {"timestamp": "t", "action": "x"},  # no audit_id
        {"audit_id": "a", "action": "x"},  # no timestamp
        {"audit_id": "", "timestamp": "t"},  # blank audit_id
        "not-a-dict",
    ]

    assert audit_spans_from_entries(entries) == []


def test_audit_missing_action_falls_back_to_generic_name() -> None:
    spans = audit_spans_from_entries([{"audit_id": "a", "timestamp": "t"}])

    assert spans[0].name == "security-audit"


# ── DualStreamTracer.collect ─────────────────────────────────────────────


def test_collect_combines_both_streams_and_indexes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {"stage": "srs"})
    _seed_event(root, "run-1", "AdapterSpawnCompleted", {"metadata": {"total_cost_usd": 0.02}})
    _seed_audit(root, _audit_entry("aud-1"))

    spans = DualStreamTracer(root).collect()
    index = TraceIndex(spans)

    # Two reasoning events share run-1 (one multi-span trace); the audit entry is
    # its own standalone trace — no fabricated cross-stream link.
    assert set(index.trace_ids()) == {"run-1", "aud-1"}
    run_spans = index.spans_for("run-1")
    assert [s.name for s in run_spans] == ["AdapterSpawnStarted", "AdapterSpawnCompleted"]
    assert all(s.kind is SpanKind.REASONING for s in run_spans)
    assert index.spans_for("aud-1")[0].kind is SpanKind.AUDIT


def test_collect_missing_events_db_yields_only_audit(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_audit(root, _audit_entry("aud-1"))

    spans = DualStreamTracer(root).collect()

    assert [s.kind for s in spans] == [SpanKind.AUDIT]
    # A read-only projection must not create the store.
    assert not (root / ".forge" / "events.db").exists()


def test_collect_corrupt_events_db_degrades_to_audit(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".forge" / "events.db").write_bytes(b"not a sqlite database\x00\xff")
    _seed_audit(root, _audit_entry("aud-1"))

    spans = DualStreamTracer(root).collect()

    # Unreadable events.db degrades to no reasoning spans, never a crash.
    assert [s.trace_id for s in spans] == ["aud-1"]


def test_collect_skips_malformed_audit_line(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_audit(root, _audit_entry("aud-1"))
    with open(root / ".forge" / "security-audit.jsonl", "a", encoding="utf-8") as handle:
        handle.write("{ partial write\n")  # crash mid-append
    _seed_audit(root, _audit_entry("aud-2"))

    spans = DualStreamTracer(root).collect()

    assert sorted(s.trace_id for s in spans) == ["aud-1", "aud-2"]


def test_collect_tolerates_non_scalar_audit_decision(tmp_path: Path) -> None:
    # Regression: a JSON-valid audit line with an unhashable `decision` must not
    # crash collect() — it degrades to a UNSET-status span, never a TypeError.
    root = _project(tmp_path)
    bad = _audit_entry("aud-1")
    bad["decision"] = {"nested": "denied"}
    _seed_audit(root, bad)

    spans = DualStreamTracer(root).collect()

    assert [s.trace_id for s in spans] == ["aud-1"]
    assert spans[0].status is SpanStatus.UNSET


def test_collect_empty_project_yields_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)

    assert DualStreamTracer(root).collect() == []


# ── DualStreamTracer.emit (default off) ──────────────────────────────────


def test_emit_disabled_by_default_writes_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})

    emitted = DualStreamTracer(root).emit()

    assert emitted == 0
    # The scaffolded sink stays empty — nothing emitted while disabled.
    assert SpanSink(root / ".forge").read_all() == []


def test_emit_enabled_writes_projection(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    _seed_audit(root, _audit_entry("aud-1"))

    tracer = DualStreamTracer(root, config=TracingConfig(enabled=True))
    emitted = tracer.emit()

    assert emitted == 2
    read = SpanSink(root / ".forge").read_all()
    assert {s.trace_id for s in read} == {"run-1", "aud-1"}


def test_emit_is_idempotent(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})

    tracer = DualStreamTracer(root, config=TracingConfig(enabled=True))
    tracer.emit()
    tracer.emit()  # re-emitting the full projection must not duplicate

    assert len(SpanSink(root / ".forge").read_all()) == 1


def test_emit_enabled_via_project_config(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    config_path = root / ".forge" / "config.yaml"
    doc = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    doc.setdefault("features", {})["tracing"] = {"enabled": True}
    config_path.write_text(yaml.safe_dump(doc), encoding="utf-8")

    # No injected config → the tracer resolves `features.tracing` from disk.
    emitted = DualStreamTracer(root).emit()

    assert emitted == 1


def test_emit_honors_injected_sink(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _seed_event(root, "run-1", "AdapterSpawnStarted", {})
    custom = SpanSink(tmp_path / "elsewhere")

    tracer = DualStreamTracer(root, config=TracingConfig(enabled=True), sink=custom)
    tracer.emit()

    assert len(custom.read_all()) == 1
