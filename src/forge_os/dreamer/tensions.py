"""Phase 10 tension detection and reflection re-ingestion (P10.06-07, FR-DR-002)."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

from forge_os.core.state_manager import utc_now
from forge_os.dreamer.timeutil import parse_timestamp
from forge_os.memory.lessons import LessonStore
from forge_os.memory.models import Lesson
from forge_os.memory.reflections import ReflectionStore

NEGATIVE_MARKERS = ("never", "avoid", "don't", "do not", "disable")
POSITIVE_MARKERS = ("always", "prefer", "ensure", "do ", "enable")
_POLARITY_WORDS = frozenset(
    {"never", "avoid", "don't", "dont", "do", "not", "always", "prefer", "ensure",
     "enable", "disable"}
)
_MIN_SHARED_WORD_LENGTH = 5
_WORD_PATTERN = re.compile(r"[a-z']+")
_MIN_STAGE_RECURRENCE = 3


def detect_tensions(lessons: list[Lesson]) -> list[dict[str, object]]:
    """Flag pairs of approved lessons that give opposite guidance about the same thing.

    Heuristic: a candidate pair shares a tag or stage_id; it is a tension when one
    text contains a negative polarity marker and the other a positive one, AND the
    texts share at least one content word of 5+ characters (lowercased, polarity
    words excluded).

    Limits: purely lexical — no negation-scope parsing, English markers only,
    substring matching can misfire (e.g. "do " inside quoted text), and surface
    word overlap yields false positives/negatives. Output is a proposal for human
    review only; nothing is changed automatically.
    """

    approved = sorted(
        (lesson for lesson in lessons if lesson.status == "approved"),
        key=lambda lesson: (lesson.created_at, lesson.id),
    )
    tensions: list[dict[str, object]] = []
    for index, lesson_a in enumerate(approved):
        for lesson_b in approved[index + 1 :]:
            if not _shares_scope(lesson_a, lesson_b):
                continue
            if not _has_opposite_polarity(lesson_a.text, lesson_b.text):
                continue
            shared_terms = _shared_content_words(lesson_a.text, lesson_b.text)
            if not shared_terms:
                continue
            tensions.append(
                {
                    "lesson_a": lesson_a.id,
                    "lesson_b": lesson_b.id,
                    "shared_terms": shared_terms,
                    "reason": (
                        "Approved lessons give opposite guidance over shared terms: "
                        f"{', '.join(shared_terms)}."
                    ),
                }
            )
    return tensions


def reingest_reflections(
    project_root: Path,
    *,
    now: str | None = None,
    window_days: float = 7.0,
) -> dict[str, object]:
    """Re-ingest recent reflections into pending lessons and record tensions.

    For any stage with >= 3 reflections inside the window, propose ONE pending
    lesson (source="reflection", confidence 0.4) unless an identical-text pending
    lesson already exists. Each detected tension is recorded as a
    `DreamerTension` reflection, skipped when an identical summary already exists.
    Idempotent: re-running with unchanged inputs changes nothing.
    """

    timestamp = now or utc_now()
    window_start = parse_timestamp(timestamp) - timedelta(days=window_days)
    reflection_store = ReflectionStore(project_root)
    lesson_store = LessonStore(project_root)

    all_reflections = reflection_store.list()
    recent = [
        reflection
        for reflection in all_reflections
        if parse_timestamp(reflection.created_at) >= window_start
    ]

    recurrence_by_stage: dict[str, int] = {}
    for reflection in recent:
        if reflection.stage_id is not None:
            recurrence_by_stage[reflection.stage_id] = (
                recurrence_by_stage.get(reflection.stage_id, 0) + 1
            )

    pending_texts = {lesson.text for lesson in lesson_store.list(status="pending")}
    lessons_proposed: list[str] = []
    for stage_id in sorted(recurrence_by_stage):
        if recurrence_by_stage[stage_id] < _MIN_STAGE_RECURRENCE:
            continue
        text = (
            f"Stage `{stage_id}` accumulated {_MIN_STAGE_RECURRENCE}+ reflections within "
            f"the last {window_days:g} days; review the recurring friction and extract "
            "a durable lesson."
        )
        if text in pending_texts:
            continue
        lesson = lesson_store.add(
            text,
            confidence=0.4,
            tags=["dreamer", "reingest"],
            stage_id=stage_id,
            source="reflection",
        )
        lessons_proposed.append(lesson.id)

    tensions = detect_tensions(lesson_store.list(status="approved"))
    existing_summaries = {reflection.summary for reflection in all_reflections}
    for tension in tensions:
        shared_terms = ", ".join(str(term) for term in tension["shared_terms"])
        summary = (
            f"Tension between lessons `{tension['lesson_a']}` and `{tension['lesson_b']}`: "
            f"opposite guidance over shared terms {shared_terms}."
        )
        if summary in existing_summaries:
            continue
        _ = reflection_store.add(
            event_type="DreamerTension",
            summary=summary,
            metadata={
                "lesson_a": tension["lesson_a"],
                "lesson_b": tension["lesson_b"],
                "shared_terms": tension["shared_terms"],
            },
        )
        existing_summaries.add(summary)

    return {
        "reflections_scanned": len(recent),
        "tensions": tensions,
        "lessons_proposed": lessons_proposed,
    }


def _shares_scope(lesson_a: Lesson, lesson_b: Lesson) -> bool:
    if lesson_a.stage_id is not None and lesson_a.stage_id == lesson_b.stage_id:
        return True
    return bool(set(lesson_a.tags) & set(lesson_b.tags))


def _has_opposite_polarity(text_a: str, text_b: str) -> bool:
    lower_a, lower_b = text_a.lower(), text_b.lower()
    a_negative = any(marker in lower_a for marker in NEGATIVE_MARKERS)
    a_positive = any(marker in lower_a for marker in POSITIVE_MARKERS)
    b_negative = any(marker in lower_b for marker in NEGATIVE_MARKERS)
    b_positive = any(marker in lower_b for marker in POSITIVE_MARKERS)
    return (a_negative and b_positive) or (a_positive and b_negative)


def _shared_content_words(text_a: str, text_b: str) -> list[str]:
    return sorted(_content_words(text_a) & _content_words(text_b))


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in _WORD_PATTERN.findall(text.lower())
        if len(word) >= _MIN_SHARED_WORD_LENGTH and word not in _POLARITY_WORDS
    }
