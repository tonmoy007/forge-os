"""Local JSONL span sink (FR-OBS-001) — the default, zero-infra trace store.

Persists neutral spans to ``.forge/traces/spans.jsonl`` so ``forge trace`` (S3)
and the optional OTLP exporter (S4) have a local source with no server required
(local-first / L004). The sink is a **materialized projection** of the two
append-only sources (Event Store + security-audit.jsonl): ``write`` replaces the
file atomically (tempfile + ``os.replace``, mirroring ``observer._write_metrics``)
rather than appending, so re-emitting the full projection is idempotent and can
never duplicate spans. ``read_all`` tolerates a partially-written / corrupt line
(mirrors ``hooks/timing.HookTimingLog.read_all``).
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from forge_os.schemas.tracing import Span


class SpanSink:
    """Atomic snapshot writer + tolerant reader for the local span store."""

    DIR_NAME = "traces"
    FILE_NAME = "spans.jsonl"

    def __init__(self, forge_path: Path) -> None:
        self.path = forge_path / self.DIR_NAME / self.FILE_NAME

    def write(self, spans: Iterable[Span]) -> None:
        """Atomically replace the sink with ``spans`` (full-snapshot projection)."""

        content = "".join(span.model_dump_json() + "\n" for span in spans)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_name(f".{self.path.name}.tmp-{uuid4()}")
        try:
            _ = temp_path.write_text(content, encoding="utf-8")
            os.replace(temp_path, self.path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise

    def read_all(self) -> list[Span]:
        """Return all valid spans, skipping any malformed/partial line."""

        if not self.path.exists():
            return []
        records: list[Span] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(Span.model_validate_json(line))
            except (ValidationError, ValueError):
                continue  # tolerate a partially-written / corrupt line
        return records
