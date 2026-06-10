"""Replay a recorded ClaudeCodeAdapter run from the Event Store (FR-ES-003).

Reconstructs the ``AgentHandle`` a spawn produced by re-projecting the recorded
event stream — ``AdapterSpawnStarted`` → N×``AdapterStreamEvent`` →
``AdapterSpawnCompleted`` — WITHOUT invoking the claude subprocess. This is the
ADR-005 determinism boundary in action: the same ``run_id`` yields the same
handle every time, derived from committed events (never re-running the kernel).

A failed run recorded only ``AdapterSpawnStarted`` + ``AdapterSpawnFailed`` and
produced no handle, so replaying it raises ``ReplayError`` (mirroring the
original spawn, which raised).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge_os.adapters.base import AgentHandle
from forge_os.adapters.claude_code.adapter import (
    EVENT_SPAWN_COMPLETED,
    EVENT_SPAWN_FAILED,
    EVENT_SPAWN_STARTED,
    EVENT_STREAM,
    extract_outputs,
)
from forge_os.adapters.claude_code.runner import RunResult, StreamEvent
from forge_os.events.store import EventStore


class ReplayError(RuntimeError):
    """Raised when a run cannot be replayed (missing, incomplete, or failed)."""


def replay_session(event_store: EventStore, run_id: str, project_root: Path) -> AgentHandle:
    """Reconstruct the AgentHandle for ``run_id`` from the recorded event stream.

    ``project_root`` anchors output-path derivation, exactly as in the live
    spawn. Raises ReplayError if the run is unknown, has no start event, never
    reached a terminal event, terminated in failure, or has a malformed /
    schema-incompatible event record (e.g. recorded by an older adapter
    version).
    """
    events = event_store.read_stream(run_id)
    if not events:
        raise ReplayError(f"no recorded run for run_id {run_id!r}")
    # One error boundary at the event-store read seam: deserialization failures
    # (missing keys from an older schema, corrupt JSON) become a domain
    # ReplayError rather than a raw KeyError/JSONDecodeError. The control-flow
    # ReplayErrors raised inside pass through untouched (not in the catch tuple).
    try:
        return _reconstruct_handle(run_id, events, project_root)
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ReplayError(
            f"run {run_id!r} has a malformed or incompatible event record: {exc}"
        ) from exc


def _reconstruct_handle(
    run_id: str, events: list[dict[str, Any]], project_root: Path
) -> AgentHandle:
    started: dict[str, Any] | None = None
    stream: list[StreamEvent] = []
    terminal: tuple[str, dict[str, Any]] | None = None

    for event in events:
        payload = json.loads(event["payload"])
        event_type = event["event_type"]
        if event_type == EVENT_SPAWN_STARTED:
            started = payload
        elif event_type == EVENT_STREAM:
            stream.append(StreamEvent(type=payload["type"], raw=payload["raw"]))
        elif event_type in (EVENT_SPAWN_COMPLETED, EVENT_SPAWN_FAILED):
            terminal = (event_type, payload)

    if started is None:
        raise ReplayError(f"run {run_id!r} has no start event")
    if terminal is None:
        raise ReplayError(f"run {run_id!r} is incomplete (no terminal event)")

    terminal_type, terminal_payload = terminal
    if terminal_type == EVENT_SPAWN_FAILED:
        raise ReplayError(
            f"run {run_id!r} failed "
            f"(returncode {terminal_payload.get('returncode')}): "
            f"{terminal_payload.get('error')}"
        )

    result = RunResult(returncode=terminal_payload["returncode"], events=stream)
    return AgentHandle(
        handle_id=terminal_payload["handle_id"],
        provider=started["adapter"],
        persona_id=started["persona_id"],
        stage_id=started.get("stage_id"),
        status=terminal_payload["status"],
        outputs=extract_outputs(result, project_root),
        metadata=terminal_payload["metadata"],
    )
