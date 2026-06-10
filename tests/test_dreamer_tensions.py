from __future__ import annotations

from pathlib import Path

from forge_os.dreamer.tensions import detect_tensions, reingest_reflections
from forge_os.memory.lessons import LessonStore
from forge_os.memory.models import Lesson
from forge_os.memory.reflections import ReflectionStore

TS = "2026-06-01T00:00:00Z"


def _lesson(text: str, *, status: str = "approved", tags: list[str] | None = None,
            stage_id: str | None = None, created_at: str = TS) -> Lesson:
    return Lesson(
        text=text,
        status=status,  # type: ignore[arg-type]
        tags=tags or [],
        stage_id=stage_id,
        created_at=created_at,
        updated_at=created_at,
    )


def test_detects_tension_between_opposite_lessons_sharing_terms() -> None:
    lesson_a = _lesson("Always enable strict validation for adapter outputs.", tags=["adapters"])
    lesson_b = _lesson(
        "Never enable strict validation for adapter outputs.",
        tags=["adapters"],
        created_at="2026-06-02T00:00:00Z",
    )

    tensions = detect_tensions([lesson_a, lesson_b])

    assert len(tensions) == 1
    assert tensions[0]["lesson_a"] == lesson_a.id
    assert tensions[0]["lesson_b"] == lesson_b.id
    assert "validation" in tensions[0]["shared_terms"]
    assert "adapter" in tensions[0]["shared_terms"]


def test_no_tension_without_shared_content_word() -> None:
    lesson_a = _lesson("Always run the suite.", tags=["ci"])
    lesson_b = _lesson("Never skip a check.", tags=["ci"], created_at="2026-06-02T00:00:00Z")

    assert detect_tensions([lesson_a, lesson_b]) == []


def test_no_tension_without_shared_tag_or_stage() -> None:
    lesson_a = _lesson("Always enable strict validation for adapters.", tags=["quality"])
    lesson_b = _lesson(
        "Never enable strict validation for adapters.",
        tags=["adapters"],
        created_at="2026-06-02T00:00:00Z",
    )

    assert detect_tensions([lesson_a, lesson_b]) == []


def test_pending_lessons_are_ignored_by_tension_detection() -> None:
    lesson_a = _lesson("Always enable strict validation for adapters.", tags=["adapters"])
    lesson_b = _lesson(
        "Never enable strict validation for adapters.",
        tags=["adapters"],
        status="pending",
        created_at="2026-06-02T00:00:00Z",
    )

    assert detect_tensions([lesson_a, lesson_b]) == []


def test_reingest_proposes_one_pending_lesson_for_recurring_stage(tmp_path: Path) -> None:
    reflections = ReflectionStore(tmp_path)
    for index in range(3):
        _ = reflections.add(
            event_type="StageCompleted",
            stage_id="srs",
            summary=f"Reflection {index} on srs.",
        )

    result = reingest_reflections(tmp_path)

    assert result["reflections_scanned"] == 3
    assert len(result["lessons_proposed"]) == 1
    pending = LessonStore(tmp_path).list(status="pending")
    assert len(pending) == 1
    assert pending[0].source == "reflection"
    assert pending[0].confidence == 0.4
    assert pending[0].tags == ["dreamer", "reingest"]
    assert pending[0].stage_id == "srs"


def test_reingest_is_idempotent_for_lessons_and_tension_reflections(tmp_path: Path) -> None:
    reflections = ReflectionStore(tmp_path)
    for index in range(3):
        _ = reflections.add(
            event_type="StageCompleted",
            stage_id="srs",
            summary=f"Reflection {index} on srs.",
        )
    lessons = LessonStore(tmp_path)
    for text in (
        "Always enable strict validation for adapter outputs.",
        "Never enable strict validation for adapter outputs.",
    ):
        _ = lessons.approve(lessons.add(text, tags=["adapters"]).id)

    first = reingest_reflections(tmp_path)
    second = reingest_reflections(tmp_path)

    assert len(first["lessons_proposed"]) == 1
    assert second["lessons_proposed"] == []
    assert len(first["tensions"]) == 1
    assert len(second["tensions"]) == 1
    assert len(lessons.list(status="pending")) == 1
    tension_reflections = [
        reflection
        for reflection in reflections.list()
        if reflection.event_type == "DreamerTension"
    ]
    assert len(tension_reflections) == 1


def test_reingest_ignores_reflections_outside_window(tmp_path: Path) -> None:
    reflections = ReflectionStore(tmp_path)
    for index in range(3):
        _ = reflections.add(
            event_type="StageCompleted",
            stage_id="srs",
            summary=f"Reflection {index} on srs.",
        )

    result = reingest_reflections(tmp_path, now="2099-01-01T00:00:00Z")

    assert result["reflections_scanned"] == 0
    assert result["lessons_proposed"] == []
    assert LessonStore(tmp_path).list(status="pending") == []


def test_reingest_requires_three_reflections_per_stage(tmp_path: Path) -> None:
    reflections = ReflectionStore(tmp_path)
    for index in range(2):
        _ = reflections.add(
            event_type="StageCompleted",
            stage_id="srs",
            summary=f"Reflection {index} on srs.",
        )

    result = reingest_reflections(tmp_path)

    assert result["reflections_scanned"] == 2
    assert result["lessons_proposed"] == []
