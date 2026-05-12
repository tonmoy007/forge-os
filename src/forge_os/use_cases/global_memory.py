"""Phase 09 global memory use cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.memory.global_store import GlobalLessonStore
from forge_os.memory.lessons import LessonStore


class GlobalMemoryUseCases:
    """Business logic for global lesson promotion and usage tracking."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.global_store = GlobalLessonStore()
        self.local_store = LessonStore(project_root)

    def list_global_lessons(self) -> list[dict[str, Any]]:
        return [
            {
                "id": le.id,
                "text": le.text[:80],
                "confidence": le.confidence,
                "tags": le.tags,
                "stage_id": le.stage_id,
                "status": le.status,
                "created_at": le.created_at,
            }
            for le in self.global_store.list_global_lessons()
        ]

    def promote_lesson(self, lesson_id: str) -> dict[str, Any] | None:
        """Promote a project-level lesson to global."""
        local = self.local_store.load()
        lesson = next((le for le in local.lessons if le.id == lesson_id), None)
        if lesson is None:
            return None
        promoted = self.global_store.promote_lesson(
            lesson,
            str(self.project_root),
        )
        return {
            "id": promoted.id,
            "text": promoted.text[:80],
            "status": promoted.status,
        }

    def get_lesson_usage(self, lesson_id: str) -> dict[str, Any] | None:
        usage = self.global_store.get_usage(lesson_id)
        if usage is None:
            return None
        return {
            "lesson_id": usage.lesson_id,
            "usage_count": usage.usage_count,
            "projects": usage.project_paths,
        }

    def suggest_promotions(self, min_projects: int = 3) -> list[dict[str, Any]]:
        return self.global_store.suggest_promotions(min_projects=min_projects)
