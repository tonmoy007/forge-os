"""Dual-stream tracer (FR-OBS-001) — builds neutral spans from the two sources.

Projects the two append-only local sources into ``Span``s:

* **Reasoning stream** — Event Store adapter/lifecycle events
  (``events/store.EventStore.read_all``). The event ``stream_id`` (= the spawn
  ``run_id``) is the ``trace_id``, so all events of one run land in one trace;
  each event becomes a span (name = event_type, start_time = created_at, kind =
  REASONING, attributes = decoded payload).
* **Audit stream** — runtime security-audit entries
  (``.forge/security-audit.jsonl``). Each entry is a standalone trace keyed by
  ``audit_id`` (kind = AUDIT).

There is no shared ``session_id`` across the two streams, so no cross-stream link
is fabricated (scope §#2c) — the ``TraceIndex`` groups exactly what the sources
carry. Reads are tolerant: a missing/unreadable ``events.db`` and malformed audit
lines degrade to fewer spans, never a crash (mirrors ``cost/aggregator``).

``emit`` is gated on ``features.tracing`` being enabled — **default off**, so an
existing project traces nothing until it opts in.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any

from forge_os.events.store import EventStore
from forge_os.schemas.tracing import Span, SpanKind, SpanStatus
from forge_os.tracing.config import TracingConfig, load_tracing_config_from_project
from forge_os.tracing.sink import SpanSink

log = logging.getLogger("forge.tracing")

# Reasoning-event outcome mapping. Explicit sets (not substring matching) so a new
# event type defaults to UNSET rather than being mis-graded by an accidental match.
_REASONING_ERROR_TYPES = frozenset({"AdapterSpawnFailed"})
_REASONING_OK_TYPES = frozenset({"AdapterSpawnCompleted"})

# Audit-decision outcome mapping (SecurityDecision values, JSON-serialized).
_AUDIT_ERROR_DECISIONS = frozenset({"denied", "failed"})
_AUDIT_OK_DECISIONS = frozenset({"allowed", "warned"})


def _decode_payload(raw: object) -> dict[str, Any]:
    """Parse an event payload (a JSON string) into attributes; ``{}`` on failure.

    A malformed payload drops only the span's attributes, not the span itself —
    the event still occurred (its structural columns are intact).
    """

    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _reasoning_status(event_type: str) -> SpanStatus:
    if event_type in _REASONING_ERROR_TYPES:
        return SpanStatus.ERROR
    if event_type in _REASONING_OK_TYPES:
        return SpanStatus.OK
    return SpanStatus.UNSET


def _audit_status(decision: object) -> SpanStatus:
    # `decision` comes from an untrusted audit line and may be any JSON type. A
    # membership test hashes the operand, so a non-scalar (list/dict) would raise
    # `TypeError: unhashable type` — guard the type first so a corrupt entry maps
    # to UNSET rather than crashing the tolerant read (mirrors the reasoning path,
    # which coerces `str(event_type)` before its membership test).
    if not isinstance(decision, str):
        return SpanStatus.UNSET
    if decision in _AUDIT_ERROR_DECISIONS:
        return SpanStatus.ERROR
    if decision in _AUDIT_OK_DECISIONS:
        return SpanStatus.OK
    return SpanStatus.UNSET


def reasoning_spans_from_rows(rows: Iterable[dict[str, Any]]) -> list[Span]:
    """Build REASONING spans from Event Store rows; skip structurally unusable ones."""

    spans: list[Span] = []
    for row in rows:
        stream_id = row.get("stream_id")
        event_id = row.get("event_id")
        event_type = row.get("event_type")
        created_at = row.get("created_at")
        # Need a trace key (stream_id), a stable span id (event_id), a name, and a
        # start time. A row missing any of these can't form a coherent span.
        if not (isinstance(stream_id, str) and stream_id):
            continue
        if event_id is None or not event_type or not created_at:
            continue
        spans.append(
            Span(
                trace_id=stream_id,
                span_id=str(event_id),
                name=str(event_type),
                kind=SpanKind.REASONING,
                start_time=str(created_at),
                status=_reasoning_status(str(event_type)),
                attributes=_decode_payload(row.get("payload")),
            )
        )
    return spans


def audit_spans_from_entries(entries: Iterable[dict[str, Any]]) -> list[Span]:
    """Build AUDIT spans from security-audit entries; one standalone trace each."""

    spans: list[Span] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        audit_id = entry.get("audit_id")
        timestamp = entry.get("timestamp")
        # audit_id is the trace/span key; timestamp is the span start. Skip an
        # entry missing either — it can't be placed on a timeline or indexed.
        if not (isinstance(audit_id, str) and audit_id) or not timestamp:
            continue
        action = entry.get("action")
        attributes = {k: v for k, v in entry.items() if k not in ("audit_id", "timestamp")}
        spans.append(
            Span(
                trace_id=audit_id,
                span_id=audit_id,
                name=str(action) if action else "security-audit",
                kind=SpanKind.AUDIT,
                start_time=str(timestamp),
                status=_audit_status(entry.get("decision")),
                attributes=attributes,
            )
        )
    return spans


class DualStreamTracer:
    """Projects the reasoning + audit sources into neutral spans and emits them.

    Dependencies are injectable for deterministic tests: ``config`` (skip the
    disk read) and ``sink`` (target a specific file). Both default to the
    project's `.forge/` layout.
    """

    def __init__(
        self,
        project_root: Path,
        *,
        config: TracingConfig | None = None,
        sink: SpanSink | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self._forge = self.project_root / ".forge"
        self._config = config
        self._sink = sink if sink is not None else SpanSink(self._forge)

    def collect(self) -> list[Span]:
        """Build the full current span set from both sources (a pure read)."""

        return [*self._reasoning_spans(), *self._audit_spans()]

    def emit(self) -> int:
        """Emit the projection to the local sink when tracing is enabled.

        Returns the number of spans written; ``0`` when tracing is disabled
        (default), in which case the sink is left untouched.
        """

        config = self._config or load_tracing_config_from_project(self.project_root)
        if not config.enabled:
            return 0
        spans = self.collect()
        self._sink.write(spans)
        return len(spans)

    # ── sources ──────────────────────────────────────────────────────────

    def _reasoning_spans(self) -> list[Span]:
        db_path = self._forge / "events.db"
        # A read-only projection must not create the store: a project that never
        # spawned has no events.db and no reasoning spans.
        if not db_path.exists():
            return []
        try:
            with closing(EventStore(db_path)) as store:
                rows = store.read_all()
        except (sqlite3.Error, OSError) as exc:
            # A present-but-unreadable events.db must degrade, not crash — tracing
            # is best-effort observability, not a control.
            log.warning("tracing: unreadable events.db at %s: %s", db_path, exc)
            return []
        return reasoning_spans_from_rows(rows)

    def _audit_spans(self) -> list[Span]:
        # SecurityAuditLog.read_all() is all-or-nothing (one bad line raises), so
        # this best-effort read parses the audit sink line-by-line and skips a
        # partially-written / corrupt line instead of losing every audit span.
        path = self._forge / "security-audit.jsonl"
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("tracing: unreadable security-audit.jsonl at %s: %s", path, exc)
            return []
        entries: list[dict[str, Any]] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(value, dict):
                entries.append(value)
        return audit_spans_from_entries(entries)
