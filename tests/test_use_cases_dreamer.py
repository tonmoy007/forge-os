from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.events.log import append_event
from forge_os.events.model import new_event
from forge_os.memory.lessons import LessonStore
from forge_os.memory.reflections import ReflectionStore
from forge_os.use_cases.dreamer import DreamerUseCases


def _seed_event(project_root: Path, timestamp: str) -> None:
    event = new_event("StageStarted", stage_id="srs")
    event.timestamp = timestamp
    append_event(project_root / ".forge" / "events.jsonl", event)


def test_digest_reports_written_path(tmp_path: Path) -> None:
    _seed_event(tmp_path, "2026-06-09T08:00:00Z")

    result = DreamerUseCases(tmp_path).digest(for_date="2026-06-09")

    assert result["written"] is True
    assert result["path"] is not None
    assert Path(str(result["path"])).exists()


def test_digest_reports_no_activity(tmp_path: Path) -> None:
    result = DreamerUseCases(tmp_path).digest(for_date="2026-06-09")

    assert result == {"written": False, "path": None}


def test_scan_proposes_lessons_from_recurring_reflections(tmp_path: Path) -> None:
    reflections = ReflectionStore(tmp_path)
    for index in range(3):
        _ = reflections.add(
            event_type="StageCompleted",
            stage_id="srs",
            summary=f"Reflection {index} on srs.",
        )

    result = DreamerUseCases(tmp_path).scan()

    assert result["reflections_scanned"] == 3
    assert len(result["lessons_proposed"]) == 1
    assert result["tensions"] == []


def test_decay_marks_stale_lessons_dormant(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson = store.add("Stale but revivable lesson.", confidence=0.9)
    _ = store.approve(lesson.id)
    document = store.load()
    document.lessons[0].last_used_at = "2000-01-01T00:00:00Z"
    store.save(document)

    result = DreamerUseCases(tmp_path).decay()

    assert result["examined"] == 1
    assert result["newly_dormant"] == 1
    assert result["dormant_ids"] == [lesson.id]
    refreshed = store.load().lessons[0]
    assert refreshed.status == "approved"
    assert refreshed.dormant is True
    assert refreshed.confidence == pytest.approx(0.0, abs=1e-9)


def test_digest_returns_error_dict_on_corrupt_event_log(tmp_path: Path) -> None:
    events_path = tmp_path / ".forge" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    _ = events_path.write_text("{not json}\n", encoding="utf-8")

    result = DreamerUseCases(tmp_path).digest(for_date="2026-06-09")

    assert result["written"] is False
    assert "error" in result
