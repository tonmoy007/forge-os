"""Domain aggregation of recorded production spend from the Event Store.

Sums ``AdapterSpawnCompleted`` events' ``metadata.total_cost_usd`` (skipping
spawns that carried no pricing), independent of any use-case/CLI layer so domain
consumers — e.g. the always-on cost-cap health checker (FR-COST-004) — can reuse
it. ``use_cases/cost.py`` produces the richer per-stage `forge cost` report; this
is the minimal "total $ so far" a cap needs.
"""

from __future__ import annotations

import json
import math
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from forge_os.events.store import EventStore

_COMPLETED = "AdapterSpawnCompleted"


@dataclass(frozen=True)
class CostTotals:
    """Aggregate recorded spend for a project."""

    total_cost_usd: float | None  # None ⇒ no priced spawn recorded
    priced_spawns: int  # spawns that carried a total_cost_usd
    total_spawns: int  # all completed spawns seen


def _as_cost(value: object) -> float | None:
    # bool is an int subclass — reject it before the numeric check.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    # A corrupt/foreign events.db can carry NaN/inf (json round-trips them) or a
    # negative cost; skip it like an unpriced spawn so it can't poison the total
    # and silently flip the cost-cap verdict to healthy.
    if not math.isfinite(number) or number < 0.0:
        return None
    return number


def _decode(raw: object) -> dict | None:
    """Parse an event payload (a JSON string) defensively; skip non-object rows."""
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


class CostAggregator:
    """Aggregate recorded production $ spend for a project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)

    def totals(self) -> CostTotals:
        db_path = self.project_root / ".forge" / "events.db"
        # A read-only aggregation must not create the store: a project that never
        # spawned has no events.db and totals to zero.
        if not db_path.exists():
            return CostTotals(total_cost_usd=None, priced_spawns=0, total_spawns=0)

        with closing(EventStore(db_path)) as store:
            completed = store.read_by_type(_COMPLETED)

        total: float | None = None
        priced = 0
        spawns = 0
        for event in completed:
            payload = _decode(event.get("payload"))
            if payload is None:
                continue
            spawns += 1
            metadata = payload.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            cost = _as_cost(metadata.get("total_cost_usd"))
            if cost is not None:
                # Sum $ only over spawns that actually carried pricing.
                total = (total or 0.0) + cost
                priced += 1

        return CostTotals(
            total_cost_usd=round(total, 6) if total is not None else None,
            priced_spawns=priced,
            total_spawns=spawns,
        )
