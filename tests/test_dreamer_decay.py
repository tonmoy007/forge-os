from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.dreamer.decay import apply_decay, decayed_confidence
from forge_os.memory.lessons import LessonStore

NOW = "2026-06-10T00:00:00Z"


def _approved_lesson(
    store: LessonStore,
    text: str,
    *,
    confidence: float,
    last_used_at: str,
) -> str:
    lesson = store.add(text, confidence=confidence)
    _ = store.approve(lesson.id)
    document = store.load()
    for item in document.lessons:
        if item.id == lesson.id:
            item.last_used_at = last_used_at
    store.save(document)
    return lesson.id


def test_decayed_confidence_halves_at_one_half_life() -> None:
    assert decayed_confidence(0.8, days_since_use=30.0) == pytest.approx(0.4)


def test_decayed_confidence_unchanged_at_zero_days() -> None:
    assert decayed_confidence(0.8, days_since_use=0.0) == pytest.approx(0.8)


def test_decayed_confidence_respects_half_life_override() -> None:
    assert decayed_confidence(1.0, days_since_use=10.0, half_life_days=10.0) == pytest.approx(0.5)


def test_apply_decay_halves_confidence_after_thirty_days(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson_id = _approved_lesson(
        store, "Keep adapters stateless.", confidence=0.8, last_used_at="2026-05-11T00:00:00Z"
    )

    summary = apply_decay(store, now=NOW)

    refreshed = next(item for item in store.load().lessons if item.id == lesson_id)
    assert refreshed.confidence == pytest.approx(0.4)
    # Exactly 30 days and 0.4 >= threshold: neither dormancy rule fires.
    assert refreshed.dormant is False
    assert summary == {"examined": 1, "decayed": 1, "newly_dormant": 0, "dormant_ids": []}


def test_apply_decay_marks_dormant_below_confidence_threshold(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson_id = _approved_lesson(
        store, "Validate inputs early.", confidence=0.32, last_used_at="2026-05-11T00:00:00Z"
    )

    summary = apply_decay(store, now=NOW)

    refreshed = next(item for item in store.load().lessons if item.id == lesson_id)
    assert refreshed.confidence == pytest.approx(0.16)
    assert refreshed.dormant is True
    assert refreshed.dormant_at == NOW
    assert summary["newly_dormant"] == 1
    assert summary["dormant_ids"] == [lesson_id]


def test_apply_decay_marks_dormant_after_dormancy_days_even_with_high_confidence(
    tmp_path: Path,
) -> None:
    store = LessonStore(tmp_path)
    lesson_id = _approved_lesson(
        store, "Prefer typed exceptions.", confidence=1.0, last_used_at="2026-05-10T00:00:00Z"
    )

    summary = apply_decay(store, now=NOW)

    refreshed = next(item for item in store.load().lessons if item.id == lesson_id)
    # 31 days since use: confidence still above threshold but staleness rule fires.
    assert refreshed.confidence > 0.3
    assert refreshed.dormant is True
    assert summary["dormant_ids"] == [lesson_id]


def test_apply_decay_never_deletes_and_never_changes_status(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    _ = _approved_lesson(
        store, "Old lesson kept for revival.", confidence=0.9, last_used_at="2025-01-01T00:00:00Z"
    )
    pending = store.add("Pending lessons stay untouched.", confidence=0.5)

    _ = apply_decay(store, now=NOW)

    lessons = store.load().lessons
    assert len(lessons) == 2
    by_id = {lesson.id: lesson for lesson in lessons}
    assert all(lesson.status in {"approved", "pending"} for lesson in lessons)
    assert by_id[pending.id].confidence == pytest.approx(0.5)
    assert by_id[pending.id].dormant is False


def test_apply_decay_is_deterministic_and_skips_dormant_lessons(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson_id = _approved_lesson(
        store, "Stale lesson goes dormant once.", confidence=0.9,
        last_used_at="2025-01-01T00:00:00Z",
    )

    first = apply_decay(store, now=NOW)
    confidence_after_first = next(
        item for item in store.load().lessons if item.id == lesson_id
    ).confidence
    second = apply_decay(store, now=NOW)

    assert first["dormant_ids"] == [lesson_id]
    assert second == {"examined": 0, "decayed": 0, "newly_dormant": 0, "dormant_ids": []}
    refreshed = next(item for item in store.load().lessons if item.id == lesson_id)
    assert refreshed.confidence == pytest.approx(confidence_after_first)


def test_decayed_confidence_rejects_non_positive_half_life() -> None:
    with pytest.raises(ValueError, match="half_life_days must be positive"):
        decayed_confidence(0.8, days_since_use=10.0, half_life_days=0.0)


def test_apply_decay_rejects_invalid_parameters(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)

    with pytest.raises(ValueError, match="dormancy_days must be positive"):
        apply_decay(store, dormancy_days=0.0)
    with pytest.raises(ValueError, match="dormancy_threshold must be within"):
        apply_decay(store, dormancy_threshold=1.5)
    with pytest.raises(ValueError, match="half_life_days must be positive"):
        apply_decay(store, half_life_days=-1.0)
