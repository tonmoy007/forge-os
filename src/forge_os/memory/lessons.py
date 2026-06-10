"""Phase 06 project lesson store."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from forge_os.core.state_manager import utc_now
from forge_os.memory.models import Lesson, LessonDocument, LessonSource, LessonStatus


class LessonStoreError(RuntimeError):
    """Raised when project lessons cannot be loaded or changed."""


class LessonStore:
    """Read and update `.forge/lessons.yaml` deterministically."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.path = self.project_root / ".forge" / "lessons.yaml"

    def load(self) -> LessonDocument:
        if not self.path.exists():
            return LessonDocument(schema_version="0.1", lessons=[])
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise LessonStoreError(f"Could not read lesson store: {self.path}") from exc
        except yaml.YAMLError as exc:
            raise LessonStoreError(f"Lesson store is not valid YAML: {self.path}") from exc

        if raw is None:
            raw = {"schema_version": "0.1", "lessons": []}
        if not isinstance(raw, dict):
            raise LessonStoreError(f"Lesson store must contain a YAML mapping: {self.path}")
        try:
            return LessonDocument.model_validate(raw)
        except ValidationError as exc:
            raise LessonStoreError(f"Invalid lesson store: {exc}") from exc

    def save(self, document: LessonDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(
            document.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )
        _ = self.path.write_text(content, encoding="utf-8")

    def list(
        self,
        *,
        status: str | None = None,
        stage_id: str | None = None,
        tag: str | None = None,
    ) -> list[Lesson]:
        lessons = self.load().lessons
        if status is not None:
            lessons = [lesson for lesson in lessons if lesson.status == status]
        if stage_id is not None:
            lessons = [lesson for lesson in lessons if lesson.stage_id in {None, stage_id}]
        if tag is not None:
            normalized_tag = tag.strip().lower()
            lessons = [lesson for lesson in lessons if normalized_tag in lesson.tags]
        return sorted(lessons, key=lambda lesson: (lesson.created_at, lesson.id))

    def add(
        self,
        text: str,
        *,
        confidence: float = 0.5,
        tags: list[str] | None = None,
        stage_id: str | None = None,
        source: str = "manual",
        status: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Lesson:
        timestamp = utc_now()
        inferred_status = "pending" if source != "manual" else "pending"
        lesson = Lesson(
            text=text,
            confidence=confidence,
            tags=tags or [],
            stage_id=stage_id,
            source=cast(LessonSource, source),
            status=cast(LessonStatus, status or inferred_status),
            created_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {},
        )
        document = self.load()
        document.lessons.append(lesson)
        self.save(document)
        return lesson

    def approve(self, lesson_id: str) -> Lesson:
        document = self.load()
        lesson = self._require_lesson(document, lesson_id)
        timestamp = utc_now()
        lesson.status = "approved"
        lesson.approved_at = timestamp
        lesson.deprecated_at = None
        lesson.updated_at = timestamp
        self.save(document)
        return lesson

    def deprecate(self, lesson_id: str) -> Lesson:
        document = self.load()
        lesson = self._require_lesson(document, lesson_id)
        timestamp = utc_now()
        lesson.status = "deprecated"
        lesson.deprecated_at = timestamp
        lesson.updated_at = timestamp
        self.save(document)
        return lesson

    def approved_for_context(
        self,
        *,
        stage_id: str | None = None,
        min_confidence: float = 0.8,
        limit: int = 5,
    ) -> list[Lesson]:
        lessons = [
            lesson
            for lesson in self.list(status="approved")
            if not lesson.dormant
            and lesson.confidence >= min_confidence
            and (lesson.stage_id is None or stage_id is None or lesson.stage_id == stage_id)
        ]
        lessons.sort(key=lambda lesson: (lesson.confidence, lesson.updated_at), reverse=True)
        return lessons[:limit]

    def render_context(
        self,
        *,
        stage_id: str | None = None,
        min_confidence: float = 0.8,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        """Render approved lessons for agent-context injection.

        SIDE EFFECT (by design, FR-ML-003): rendering counts as *usage* —
        each returned lesson gets ``last_used_at`` refreshed and ``use_count``
        incremented, and the store is persisted. The Dreamer's decay reads
        these fields, so injection keeps a lesson's confidence alive.
        """
        selected_ids = [
            lesson.id
            for lesson in self.approved_for_context(
                stage_id=stage_id,
                min_confidence=min_confidence,
                limit=limit,
            )
        ]
        if not selected_ids:
            return []

        # Injection into agent context counts as usage (FR-ML-003 decay input).
        document = self.load()
        timestamp = utc_now()
        rendered: dict[str, dict[str, object]] = {}
        for lesson in document.lessons:
            if lesson.id not in selected_ids:
                continue
            lesson.last_used_at = timestamp
            lesson.use_count += 1
            rendered[lesson.id] = {
                "id": lesson.id,
                "text": lesson.text,
                "confidence": lesson.confidence,
                "tags": lesson.tags,
                "stage_id": lesson.stage_id,
            }
        self.save(document)
        return [rendered[lesson_id] for lesson_id in selected_ids]

    def revive(self, lesson_id: str) -> Lesson:
        """Clear dormancy so an approved lesson re-enters context selection (FR-DR-003)."""

        document = self.load()
        lesson = self._require_lesson(document, lesson_id)
        lesson.dormant = False
        lesson.dormant_at = None
        lesson.updated_at = utc_now()
        self.save(document)
        return lesson

    def _require_lesson(self, document: LessonDocument, lesson_id: str) -> Lesson:
        for lesson in document.lessons:
            if lesson.id == lesson_id:
                return lesson
        raise LessonStoreError(f"Unknown lesson `{lesson_id}`.")
