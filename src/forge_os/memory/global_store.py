"""Phase 09 global memory store under ~/.forge/.

Global lessons are cross-project lessons that have been promoted from
project-level lessons. Usage tracking records which projects use which
lessons to enable automatic promotion suggestions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from forge_os.core.state_manager import utc_now
from forge_os.memory.models import Lesson


class GlobalLessonUsage(BaseModel):
    """Tracks which projects have used a global lesson."""

    lesson_id: str
    project_paths: list[str] = Field(default_factory=list)
    usage_count: int = 0
    first_used_at: str = ""
    last_used_at: str = ""


class GlobalMemoryDocument(BaseModel):
    """Top-level document for ~/.forge/memory.yaml."""

    schema_version: str = "0.1"
    global_lessons: list[Lesson] = Field(default_factory=list)
    usage: list[GlobalLessonUsage] = Field(default_factory=list)


def get_global_forge_dir() -> Path:
    """Return ~/.forge/, creating it if needed."""
    path = Path.home() / ".forge"
    path.mkdir(parents=True, exist_ok=True)
    return path


class GlobalLessonStore:
    """Manage ~/.forge/memory.yaml — cross-project lessons and usage tracking."""

    def __init__(self) -> None:
        self.path = get_global_forge_dir() / "memory.yaml"

    def load(self) -> GlobalMemoryDocument:
        if not self.path.exists():
            return GlobalMemoryDocument()
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except OSError:
            return GlobalMemoryDocument()
        except yaml.YAMLError:
            return GlobalMemoryDocument()
        if not isinstance(raw, dict):
            return GlobalMemoryDocument()
        try:
            return GlobalMemoryDocument.model_validate(raw)
        except ValidationError:
            return GlobalMemoryDocument()

    def save(self, document: GlobalMemoryDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(
            document.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )
        self.path.write_text(content, encoding="utf-8")

    def list_global_lessons(self) -> list[Lesson]:
        return self.load().global_lessons

    def promote_lesson(
        self,
        lesson: Lesson,
        project_path: str,
    ) -> Lesson:
        """Promote a project-level lesson to global."""
        document = self.load()

        # Check if already exists (by text de-duplication)
        existing = next(
            (le for le in document.global_lessons if le.text == lesson.text),
            None,
        )
        if existing is not None:
            self._record_usage(document, existing.id, project_path)
            self.save(document)
            return existing

        timestamp = utc_now()
        global_lesson = Lesson(
            text=lesson.text,
            confidence=lesson.confidence,
            tags=list(lesson.tags),
            stage_id=lesson.stage_id,
            source="manual",
            status="approved",
            created_at=timestamp,
            updated_at=timestamp,
            metadata={
                "promoted_from": project_path,
                "original_id": lesson.id,
            },
        )
        document.global_lessons.append(global_lesson)
        self._record_usage(document, global_lesson.id, project_path)
        self.save(document)
        return global_lesson

    def get_usage(self, lesson_id: str) -> GlobalLessonUsage | None:
        document = self.load()
        for u in document.usage:
            if u.lesson_id == lesson_id:
                return u
        return None

    def suggest_promotions(self, min_projects: int = 3) -> list[dict[str, Any]]:
        """Suggest lessons used across N+ projects for global promotion."""
        document = self.load()
        suggestions: list[dict[str, Any]] = []
        for u in document.usage:
            if u.usage_count >= min_projects:
                matched = next(
                    (le for le in document.global_lessons if le.id == u.lesson_id),
                    None,
                )
                if matched is None:
                    continue
                suggestions.append({
                    "lesson_id": matched.id,
                    "text": matched.text[:80],
                    "usage_count": u.usage_count,
                    "projects": u.project_paths,
                })
        return suggestions

    def _record_usage(
        self, document: GlobalMemoryDocument, lesson_id: str, project_path: str
    ) -> None:
        timestamp = utc_now()
        for u in document.usage:
            if u.lesson_id == lesson_id:
                if project_path not in u.project_paths:
                    u.project_paths.append(project_path)
                u.usage_count = len(u.project_paths)
                u.last_used_at = timestamp
                return
        document.usage.append(
            GlobalLessonUsage(
                lesson_id=lesson_id,
                project_paths=[project_path],
                usage_count=1,
                first_used_at=timestamp,
                last_used_at=timestamp,
            )
        )
