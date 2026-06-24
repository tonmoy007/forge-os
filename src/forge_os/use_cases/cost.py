"""Use case for `forge cost` — aggregate recorded spawn token/$ spend.

Reads the Event Store's ``AdapterSpawnCompleted`` events (which carry
``metadata.usage`` + ``metadata.total_cost_usd``) and joins them to
``AdapterSpawnStarted`` by ``run_id`` (the stream id) for stage attribution —
the Completed event has no ``stage_id``, only Started does.

Depends on F0 (the production spawn path now records these events); against a
project with no recorded spawns the report is simply empty.
"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from forge_os.events.store import EventStore
from forge_os.schemas.cost import CostReport, StageCost

_STARTED = "AdapterSpawnStarted"
_COMPLETED = "AdapterSpawnCompleted"
_UNATTRIBUTED = "(unattributed)"


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _as_cost(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _round_cost(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _as_stage(value: object) -> str | None:
    """Coerce a recorded stage_id to a string key (None for any other type)."""
    return value if isinstance(value, str) else None


def _decode(raw: object) -> dict | None:
    """Parse an event payload (a JSON string) defensively.

    The Event Store is being grown toward authority and may accumulate
    externally-written or schema-drifted rows, so a single malformed/non-object
    payload is skipped rather than crashing the whole report.
    """
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


class _Bucket:
    """Running totals for one stage."""

    def __init__(self) -> None:
        self.spawns = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd: float | None = None

    def add(self, input_tokens: int, output_tokens: int, cost: float | None) -> None:
        self.spawns += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        if cost is not None:
            # Sum $ only over spawns that actually carried pricing.
            self.cost_usd = (self.cost_usd or 0.0) + cost


class CostUseCases:
    """Aggregate recorded production spawn spend into a :class:`CostReport`."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def report(self, *, stage_filter: str | None = None) -> CostReport:
        db_path = self.project_root / ".forge" / "events.db"
        # A read-only report must not create the store: a project that never
        # spawned has no events.db and yields an empty (valid) report.
        if not db_path.exists():
            return CostReport()

        with closing(EventStore(db_path)) as store:
            started = store.read_by_type(_STARTED)
            completed = store.read_by_type(_COMPLETED)

        stage_by_run: dict[str, str | None] = {}
        for event in started:
            payload = _decode(event["payload"])
            if payload is not None:
                stage_by_run[event["stream_id"]] = _as_stage(payload.get("stage_id"))

        buckets: dict[str, _Bucket] = {}
        adapters: set[str] = set()
        for event in completed:
            payload = _decode(event["payload"])
            if payload is None:
                continue
            stage = stage_by_run.get(event["stream_id"]) or _UNATTRIBUTED
            if stage_filter is not None and stage != stage_filter:
                continue
            metadata = payload.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            usage = metadata.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            adapter = payload.get("adapter")
            if isinstance(adapter, str) and adapter:
                adapters.add(adapter)
            buckets.setdefault(stage, _Bucket()).add(
                _as_int(usage.get("input_tokens")),
                _as_int(usage.get("output_tokens")),
                _as_cost(metadata.get("total_cost_usd")),
            )

        stages = [
            StageCost(
                stage_id=stage,
                spawns=bucket.spawns,
                input_tokens=bucket.input_tokens,
                output_tokens=bucket.output_tokens,
                total_tokens=bucket.input_tokens + bucket.output_tokens,
                cost_usd=_round_cost(bucket.cost_usd),
            )
            for stage, bucket in sorted(buckets.items())
        ]
        priced = [stage.cost_usd for stage in stages if stage.cost_usd is not None]
        total_input = sum(stage.input_tokens for stage in stages)
        total_output = sum(stage.output_tokens for stage in stages)
        return CostReport(
            stages=stages,
            adapters=sorted(adapters),
            production_spawns=sum(stage.spawns for stage in stages),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            total_cost_usd=round(sum(priced), 6) if priced else None,
        )
