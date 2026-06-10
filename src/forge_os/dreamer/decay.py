"""Phase 10 lesson confidence decay and dormancy (P10.08-09, FR-ML-003)."""

from __future__ import annotations

from forge_os.core.state_manager import utc_now
from forge_os.dreamer.timeutil import parse_timestamp
from forge_os.memory.lessons import LessonStore

SECONDS_PER_DAY = 86400.0


def decayed_confidence(
    confidence: float,
    *,
    days_since_use: float,
    half_life_days: float = 30.0,
) -> float:
    """Exponentially decay *confidence* with the given half-life, floored at 0.0."""

    if half_life_days <= 0:
        raise ValueError(f"half_life_days must be positive, got {half_life_days}")
    return max(confidence * 0.5 ** (days_since_use / half_life_days), 0.0)


def apply_decay(
    store: LessonStore,
    *,
    now: str | None = None,
    half_life_days: float = 30.0,
    dormancy_threshold: float = 0.3,
    dormancy_days: float = 30.0,
) -> dict[str, object]:
    """Decay approved lessons and mark stale ones dormant. Proposes only — never deletes.

    Dormancy is reversible (`LessonStore.revive`) and never changes lesson status.
    Deterministic when *now* is injected (ISO-8601 Z timestamp). All mutations are
    applied in memory and persisted with ONE save at the end, so a write failure
    leaves the store untouched rather than partially decayed.
    """

    if half_life_days <= 0:
        raise ValueError(f"half_life_days must be positive, got {half_life_days}")
    if dormancy_days <= 0:
        raise ValueError(f"dormancy_days must be positive, got {dormancy_days}")
    if not 0.0 <= dormancy_threshold <= 1.0:
        raise ValueError(
            f"dormancy_threshold must be within [0, 1], got {dormancy_threshold}"
        )

    timestamp = now or utc_now()
    reference_now = parse_timestamp(timestamp)
    document = store.load()
    examined = 0
    decayed = 0
    dormant_ids: list[str] = []

    for lesson in document.lessons:
        if lesson.status != "approved" or lesson.dormant:
            continue
        examined += 1
        last_used = lesson.last_used_at or lesson.approved_at or lesson.updated_at
        elapsed = (reference_now - parse_timestamp(last_used)).total_seconds()
        days_since_use = max(elapsed / SECONDS_PER_DAY, 0.0)
        new_confidence = decayed_confidence(
            lesson.confidence,
            days_since_use=days_since_use,
            half_life_days=half_life_days,
        )
        if new_confidence < lesson.confidence:
            decayed += 1
        lesson.confidence = new_confidence
        if new_confidence < dormancy_threshold or days_since_use > dormancy_days:
            lesson.dormant = True
            lesson.dormant_at = timestamp
            dormant_ids.append(lesson.id)

    store.save(document)
    return {
        "examined": examined,
        "decayed": decayed,
        "newly_dormant": len(dormant_ids),
        "dormant_ids": dormant_ids,
    }
