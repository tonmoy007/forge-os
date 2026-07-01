"""Optional OTLP exporter for neutral spans (FR-OBS-001 — S4).

Converts the dual-stream projection's neutral :class:`Span`s into OpenTelemetry
``ReadableSpan``s and ships them to a configured OTLP collector. This is the one
part of the tracing workstream that needs a third-party dependency, so it lives
behind the optional ``[tracing]`` extra: the module imports cleanly without
``opentelemetry`` installed (``otlp_available()`` reports ``False``) and every
OTEL reference is deferred to call time. The local JSONL sink + ``forge trace``
work without this extra — OTLP is purely additive and off by default (L004).

Neutral ids are arbitrary strings (run_id / audit_id / event_id), so they are
hashed **deterministically** (SHA-256, no randomness) to OTLP's 128-bit trace id
and 64-bit span id — the same source id always maps to the same OTLP id across
runs, which is what makes the two streams correlate in a backend.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from forge_os.schemas.tracing import Span, SpanKind, SpanStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from opentelemetry.sdk.trace import ReadableSpan

log = logging.getLogger("forge.tracing.otlp")

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan as _ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.trace import SpanContext, TraceFlags
    from opentelemetry.trace import SpanKind as OTELSpanKind
    from opentelemetry.trace.status import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # the optional `[tracing]` extra is not installed
    _OTEL_AVAILABLE = False

_SERVICE_NAME = "forge-os"
# OTLP encodes integer attributes as protobuf int64; an out-of-range int (e.g. a
# uint64 identifier decoded from a JSON payload) is silently DROPPED by the
# encoder. Such ints are JSON-stringified instead so no attribute is lost.
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


def _is_otel_scalar(value: object) -> bool:
    """True when the SDK/OTLP encoder accepts ``value`` as a scalar attribute."""

    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return _INT64_MIN <= value <= _INT64_MAX
    return isinstance(value, (float, str))


class OTLPUnavailableError(RuntimeError):
    """Raised when OTLP export is requested but the `[tracing]` extra is absent."""


def otlp_available() -> bool:
    """True when the optional OpenTelemetry OTLP dependency is importable."""

    return _OTEL_AVAILABLE


def _hashed_id(value: str, *, byte_length: int) -> int:
    """Deterministically map an arbitrary id string to a non-zero OTLP int id.

    OTEL rejects an all-zero trace/span id, so a (vanishingly unlikely) zero hash
    is bumped to 1. SHA-256 is stable across runs, so the same source id always
    yields the same OTLP id — the property that lets a backend stitch the streams.
    """

    digest = hashlib.sha256(value.encode("utf-8")).digest()[:byte_length]
    return int.from_bytes(digest, "big") or 1


def _epoch_nanos(timestamp: str) -> int:
    """RFC 3339 (`…Z`) or naive-local timestamp → epoch nanoseconds; 0 if unparseable.

    Mirrors the S3 chronological parse (naive treated as machine-local). A span with
    an unparseable time still exports (at epoch 0) rather than being dropped silently.
    """

    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return int(parsed.timestamp() * 1_000_000_000)


def _otel_kind(kind: SpanKind) -> OTELSpanKind:
    # Both streams are internal activity (not RPC client/server spans).
    return OTELSpanKind.INTERNAL


def _otel_status(status: SpanStatus) -> Status:
    if status is SpanStatus.OK:
        return Status(StatusCode.OK)
    if status is SpanStatus.ERROR:
        return Status(StatusCode.ERROR)
    return Status(StatusCode.UNSET)


def _otel_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Coerce arbitrary span attributes to OTEL-valid values.

    Scalars and homogeneous scalar sequences pass through; anything else (nested
    dict, mixed list, None) is JSON-stringified so no attribute is dropped or
    rejected by the SDK. Keys are coerced to ``str``.
    """

    result: dict[str, Any] = {}
    for key, value in attributes.items():
        name = str(key)
        if _is_otel_scalar(value):
            result[name] = value
        elif isinstance(value, (list, tuple)) and all(_is_otel_scalar(v) for v in value):
            result[name] = list(value)
        else:
            # nested/heterogeneous/None/out-of-int64-range → a stringified value the
            # encoder always accepts, so no attribute is dropped.
            result[name] = json.dumps(value, ensure_ascii=False, default=str)
    return result


def _to_readable_span(span: Span, resource: Any) -> ReadableSpan:
    trace_id = _hashed_id(span.trace_id, byte_length=16)
    context = SpanContext(
        trace_id=trace_id,
        span_id=_hashed_id(span.span_id, byte_length=8),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    parent = None
    if span.parent_span_id:
        # A parent lives in the same trace; only its span id differs.
        parent = SpanContext(
            trace_id=trace_id,
            span_id=_hashed_id(span.parent_span_id, byte_length=8),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    start = _epoch_nanos(span.start_time)
    end = _epoch_nanos(span.end_time) if span.end_time else start
    return _ReadableSpan(
        name=span.name,
        context=context,
        parent=parent,
        resource=resource,
        attributes=_otel_attributes(span.attributes),
        kind=_otel_kind(span.kind),
        status=_otel_status(span.status),
        start_time=start,
        end_time=end,
    )


def export_spans(
    spans: Iterable[Span],
    endpoint: str,
    *,
    exporter: SpanExporter | None = None,
) -> bool:
    """Export neutral spans to an OTLP collector; return True on success.

    ``exporter`` is injectable so tests use an in-memory exporter (no network).
    Raises :class:`OTLPUnavailableError` when the `[tracing]` extra is absent and
    no exporter is injected — the daemon gate checks ``otlp_available()`` first, so
    this only fires on direct misuse.
    """

    if exporter is None:
        if not _OTEL_AVAILABLE:
            raise OTLPUnavailableError(
                "OTLP export requires the optional `[tracing]` extra "
                "(pip install 'forge-os[tracing]')."
            )
        exporter = OTLPSpanExporter(endpoint=endpoint)

    resource = Resource.create({"service.name": _SERVICE_NAME})
    readable: Sequence[ReadableSpan] = [_to_readable_span(span, resource) for span in spans]
    result = exporter.export(readable)
    return result == SpanExportResult.SUCCESS
