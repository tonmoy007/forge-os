"""Correlation/trace index over neutral spans (FR-OBS-001, FR-SEM-002).

Groups a flat collection of ``Span``s into traces (by ``trace_id``) and returns
them in a stable, time-ordered form — the lookup ``forge trace <id>`` renders.
Correlation is honest: reasoning spans that share a run_id land in one trace;
audit spans (each its own audit_id trace_id) stand alone. The index never
fabricates a cross-stream link the sources don't carry (scope §#2c).
"""

from __future__ import annotations

from collections.abc import Iterable

from forge_os.schemas.tracing import Span


class TraceIndex:
    """Index spans by ``trace_id`` for ordered per-trace retrieval."""

    def __init__(self, spans: Iterable[Span]) -> None:
        self._by_trace: dict[str, list[Span]] = {}
        for span in spans:
            self._by_trace.setdefault(span.trace_id, []).append(span)
        # Stable time order within a trace. start_time is RFC 3339, so a
        # lexicographic sort is chronological; span_id breaks ties deterministically
        # and Python's stable sort preserves insertion order for full ties.
        for trace_spans in self._by_trace.values():
            trace_spans.sort(key=lambda s: (s.start_time, s.span_id))

    def trace_ids(self) -> list[str]:
        """All trace ids, in first-seen order."""
        return list(self._by_trace)

    def spans_for(self, trace_id: str) -> list[Span]:
        """Spans in ``trace_id``, time-ordered; empty list for an unknown trace.

        Returns a fresh list, so a caller cannot mutate the index's internal order.
        """
        return list(self._by_trace.get(trace_id, []))
