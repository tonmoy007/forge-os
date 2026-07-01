"""Tests for the optional OTLP exporter (FR-OBS-001 — S4).

The `[tracing]` extra is part of the `dev` extra, so OpenTelemetry is importable
here; export is exercised with an in-memory exporter (no network).
"""

from __future__ import annotations

import json
from datetime import UTC

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind as OTELSpanKind
from opentelemetry.trace.status import StatusCode

from forge_os.schemas.tracing import Span, SpanKind, SpanStatus
from forge_os.tracing import otlp
from forge_os.tracing.otlp import (
    OTLPUnavailableError,
    _epoch_nanos,
    _hashed_id,
    _otel_attributes,
    _to_readable_span,
    export_spans,
    otlp_available,
)


def _span(
    trace_id: str = "run-1",
    span_id: str = "1",
    *,
    kind: SpanKind = SpanKind.REASONING,
    status: SpanStatus = SpanStatus.OK,
    start: str = "2026-07-01T00:00:01.000Z",
    attributes: dict | None = None,
) -> Span:
    return Span(
        trace_id=trace_id,
        span_id=span_id,
        name="AdapterSpawnCompleted",
        kind=kind,
        start_time=start,
        status=status,
        attributes=attributes or {},
    )


def test_otlp_is_available_under_dev_extra() -> None:
    assert otlp_available() is True


def test_hashed_id_is_deterministic_nonzero_and_bounded() -> None:
    a = _hashed_id("run-1", byte_length=16)
    b = _hashed_id("run-1", byte_length=16)
    assert a == b  # stable across calls — required for cross-run correlation
    assert 0 < a < 2**128
    span_id = _hashed_id("1", byte_length=8)
    assert 0 < span_id < 2**64
    assert _hashed_id("run-2", byte_length=16) != a  # different source ⇒ different id


def test_epoch_nanos_utc_and_unparseable() -> None:
    from datetime import UTC, datetime

    expected = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1_000_000_000)
    assert _epoch_nanos("2026-07-01T00:00:00Z") == expected
    assert _epoch_nanos("not-a-timestamp") == 0  # degrades, never raises


def test_epoch_nanos_naive_is_local_not_utc() -> None:
    # Pin a POSIX offset TZ (no tzdata needed) so naive-as-local is distinguishable
    # from naive-as-UTC — the assertion is tautological on a UTC host (Docker/CI).
    import os
    import time
    from datetime import datetime

    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "XXX-5"  # local = UTC+5, no DST
    time.tzset()
    try:
        naive = "2026-07-01T12:00:00"
        as_local = int(datetime.fromisoformat(naive).astimezone().timestamp() * 1_000_000_000)
        as_utc = int(
            datetime.fromisoformat(naive).replace(tzinfo=UTC).timestamp() * 1_000_000_000
        )
        assert as_local != as_utc  # the TZ pin actually decouples the two readings
        assert _epoch_nanos(naive) == as_local  # naive parsed as LOCAL, not UTC
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()


def test_otel_attributes_coercion() -> None:
    attrs = _otel_attributes(
        {
            "s": "x",
            "n": 3,
            "f": 1.5,
            "b": True,
            "scalar_list": [1, 2, 3],
            "nested": {"k": "v"},
            "mixed": [1, {"a": 1}],
            "none": None,
        }
    )
    assert attrs["s"] == "x" and attrs["n"] == 3 and attrs["f"] == 1.5 and attrs["b"] is True
    assert attrs["scalar_list"] == [1, 2, 3]
    assert attrs["nested"] == '{"k": "v"}'  # non-scalar → JSON string
    assert attrs["mixed"] == '[1, {"a": 1}]'  # heterogeneous list → JSON string
    assert attrs["none"] == "null"


def test_out_of_int64_range_int_is_stringified() -> None:
    # OTLP encodes ints as protobuf int64; an out-of-range int is silently dropped
    # by the encoder, so it must be stringified to survive (in-range ints stay ints).
    attrs = _otel_attributes(
        {"max_ok": 2**63 - 1, "min_ok": -(2**63), "over": 2**63, "under": -(2**63) - 1}
    )
    assert attrs["max_ok"] == 2**63 - 1
    assert attrs["min_ok"] == -(2**63)
    assert attrs["over"] == json.dumps(2**63)
    assert attrs["under"] == json.dumps(-(2**63) - 1)


def test_out_of_range_int_in_list_stringifies_whole_list() -> None:
    attrs = _otel_attributes({"ids": [1, 2**63]})
    assert attrs["ids"] == json.dumps([1, 2**63])


def test_converted_span_encodes_without_dropping_attributes() -> None:
    # End-to-end: a uint64-scale attribute must survive real OTLP proto encoding.
    # Without the int64 guard the encoder silently drops it (verified via the
    # in-memory exporter never proto-encoding, so this pins the actual wire path).
    from opentelemetry.exporter.otlp.proto.common._internal.trace_encoder import encode_spans
    from opentelemetry.sdk.resources import Resource

    span = _span(attributes={"external_id": 2**64 - 1})
    readable = _to_readable_span(span, Resource.create({}))

    encoded = encode_spans([readable])
    keys = [kv.key for kv in encoded.resource_spans[0].scope_spans[0].spans[0].attributes]
    assert "external_id" in keys


def test_to_readable_span_maps_fields() -> None:
    span = _span(status=SpanStatus.ERROR, attributes={"stage": "srs"})
    from opentelemetry.sdk.resources import Resource

    readable = _to_readable_span(span, Resource.create({"service.name": "forge-os"}))

    assert readable.name == "AdapterSpawnCompleted"
    assert readable.context.trace_id == _hashed_id("run-1", byte_length=16)
    assert readable.context.span_id == _hashed_id("1", byte_length=8)
    assert readable.parent is None
    assert readable.kind is OTELSpanKind.INTERNAL
    assert readable.status.status_code is StatusCode.ERROR
    assert readable.start_time == readable.end_time  # no end_time ⇒ start
    assert dict(readable.attributes) == {"stage": "srs"}


def test_status_mapping() -> None:
    from opentelemetry.sdk.resources import Resource

    resource = Resource.create({})

    def code(status: SpanStatus) -> StatusCode:
        return _to_readable_span(_span(status=status), resource).status.status_code

    assert code(SpanStatus.OK) is StatusCode.OK
    assert code(SpanStatus.ERROR) is StatusCode.ERROR
    assert code(SpanStatus.UNSET) is StatusCode.UNSET


def test_parent_span_context_shares_trace_id() -> None:
    from opentelemetry.sdk.resources import Resource

    span = _span()
    span = span.model_copy(update={"parent_span_id": "0"})
    readable = _to_readable_span(span, Resource.create({}))

    assert readable.parent is not None
    assert readable.parent.trace_id == readable.context.trace_id
    assert readable.parent.span_id == _hashed_id("0", byte_length=8)


def test_export_spans_via_injected_exporter() -> None:
    exporter = InMemorySpanExporter()
    spans = [_span(trace_id="run-1", span_id="1"), _span(trace_id="aud-1", span_id="aud-1")]

    ok = export_spans(spans, "http://unused", exporter=exporter)

    assert ok is True
    finished = exporter.get_finished_spans()
    assert [s.name for s in finished] == ["AdapterSpawnCompleted", "AdapterSpawnCompleted"]
    assert finished[0].context.trace_id == _hashed_id("run-1", byte_length=16)


def test_export_empty_span_list_succeeds() -> None:
    exporter = InMemorySpanExporter()
    assert export_spans([], "http://unused", exporter=exporter) is True
    assert exporter.get_finished_spans() == ()


def test_export_without_exporter_raises_when_extra_absent(monkeypatch) -> None:
    # Simulate the `[tracing]` extra being uninstalled.
    monkeypatch.setattr(otlp, "_OTEL_AVAILABLE", False)
    try:
        export_spans([_span()], "http://collector:4318/v1/traces")
    except OTLPUnavailableError:
        pass
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("expected OTLPUnavailableError when the extra is absent")


def test_base_install_imports_without_opentelemetry() -> None:
    # L004 crux: with the `[tracing]` extra absent, the module (and everything that
    # imports it: daemon tasks, the CLI) must import cleanly and report unavailable.
    # A subprocess with opentelemetry blocked proves this for real — monkeypatching
    # `_OTEL_AVAILABLE` does NOT (opentelemetry is installed under the dev extra).
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        sys.modules["opentelemetry"] = None  # block every opentelemetry.* import
        import forge_os.tracing.otlp as otlp
        import forge_os.daemon.tasks  # imports otlp lazily — must not need the extra
        from forge_os.cli.main import app  # base CLI must load without the extra
        assert otlp.otlp_available() is False
        try:
            otlp.export_spans([], "http://collector:4318/v1/traces")
        except otlp.OTLPUnavailableError:
            print("IMPORT_SAFE_OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "IMPORT_SAFE_OK" in result.stdout
