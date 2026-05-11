"""JSON Lines event log helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from forge_os.events.model import LifecycleEvent


class EventLogError(RuntimeError):
    """Raised when the event log cannot be read or written."""


def append_event(path: Path, event: LifecycleEvent) -> None:
    """Append one normalized event to a JSONL event log."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as event_log:
        _ = event_log.write(json.dumps(event.model_dump(), sort_keys=False) + "\n")


def read_events(path: Path) -> list[LifecycleEvent]:
    """Read normalized events from a JSONL event log."""

    if not path.exists():
        return []

    events: list[LifecycleEvent] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(LifecycleEvent.model_validate_json(line))
        except (ValueError, ValidationError) as exc:
            raise EventLogError(f"Invalid event log line {line_number} in {path}") from exc
    return events


def filter_events(
    events: Iterable[LifecycleEvent],
    *,
    event_type: str | None = None,
    stage_id: str | None = None,
) -> list[LifecycleEvent]:
    """Return events filtered by optional type/stage."""

    filtered: list[LifecycleEvent] = []
    for event in events:
        if event_type is not None and event.event_type != event_type:
            continue
        if stage_id is not None and event.stage_id != stage_id:
            continue
        filtered.append(event)
    return filtered
