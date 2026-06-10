"""Phase 10 Dreamer use cases (P10.05-09)."""

from __future__ import annotations

from pathlib import Path

from forge_os.dreamer.decay import apply_decay
from forge_os.dreamer.digest import DailyDigestWriter
from forge_os.dreamer.tensions import reingest_reflections
from forge_os.events.log import EventLogError
from forge_os.memory.lessons import LessonStore, LessonStoreError
from forge_os.memory.reflections import ReflectionStoreError


class DreamerUseCases:
    """Bridge Dreamer maintenance routines to the CLI as plain dicts."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def digest(self, for_date: str | None = None) -> dict[str, object]:
        try:
            path = DailyDigestWriter(self.project_root).write(for_date=for_date)
        except (EventLogError, OSError) as exc:
            return {"written": False, "path": None, "error": str(exc)}
        return {"written": path is not None, "path": str(path) if path else None}

    def scan(self) -> dict[str, object]:
        try:
            return reingest_reflections(self.project_root)
        except (LessonStoreError, ReflectionStoreError) as exc:
            return {"error": str(exc)}

    def decay(self) -> dict[str, object]:
        try:
            return apply_decay(LessonStore(self.project_root))
        except LessonStoreError as exc:
            return {"error": str(exc)}
