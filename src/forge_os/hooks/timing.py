"""Hook execution-timing record + durable sink (FR-HD-005 prerequisite).

Records per-invocation hook latency to an append-only ``.forge/hook-timings.jsonl``
so the daemon's hook-latency health check (a later slice) can flag persistently
slow hooks. Recording is best-effort and lives outside hook-dispatch correctness
— a write failure must never affect hook execution or state.

Intentionally imports only stdlib + pydantic (no ``forge_os`` imports): this
module is reached from ``events.bus``, which is itself imported by
``core.state_manager``, so any back-import would create a cycle.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class HookTiming(BaseModel):
    """One hook invocation's latency, persisted to ``.forge/hook-timings.jsonl``."""

    event_type: str
    hook_name: str
    status: str
    duration_ms: float
    recorded_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class HookTimingLog:
    """Append-only sink + reader for hook timings under ``.forge/``."""

    FILE_NAME = "hook-timings.jsonl"

    def __init__(self, forge_path: Path) -> None:
        self.path = forge_path / self.FILE_NAME

    def append(self, timings: Iterable[HookTiming]) -> None:
        """Append timing records. Callers treat recording as best-effort."""

        lines = "".join(timing.model_dump_json() + "\n" for timing in timings)
        if not lines:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(lines)

    def read_all(self) -> list[HookTiming]:
        """Return all valid records, skipping any malformed/partial line."""

        if not self.path.exists():
            return []
        records: list[HookTiming] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(HookTiming.model_validate_json(line))
            except (ValidationError, ValueError):
                continue  # tolerate a partially-written / corrupt line
        return records
