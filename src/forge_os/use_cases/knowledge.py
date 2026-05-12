"""Knowledge integrity scanning and token budget reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.context.registry import ArtifactRegistry
from forge_os.memory.lessons import LessonStore


class KnowledgeUseCases:
    """Scan lessons for integrity issues and report token budgets."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def scan_lesson_references(self) -> list[dict[str, Any]]:
        """Scan lessons for references to artifacts that no longer exist."""
        store = LessonStore(self.project_root)
        lessons = store.list()
        registry = ArtifactRegistry(self.project_root)
        document = registry.load()
        existing_paths = {a.path for a in document.artifacts}

        issues: list[dict[str, Any]] = []
        for lesson in lessons:
            for ref in self._extract_references(lesson.text):
                if ref not in existing_paths:
                    issues.append({
                        "lesson_id": lesson.id,
                        "reference": ref,
                        "issue": "missing_artifact",
                        "lesson_text": lesson.text[:80],
                    })
        return issues

    def scan_lesson_conflicts(self) -> list[dict[str, Any]]:
        """Scan for duplicate or conflicting lessons."""
        store = LessonStore(self.project_root)
        lessons = store.list()

        conflicts: list[dict[str, Any]] = []
        seen: dict[str, list[str]] = {}
        for lesson in lessons:
            key = lesson.text.strip().lower()
            if key in seen:
                conflicts.append({
                    "existing_id": seen[key][0],
                    "duplicate_id": lesson.id,
                    "text": lesson.text[:80],
                    "issue": "duplicate_lesson",
                })
            seen.setdefault(key, []).append(lesson.id)
        return conflicts

    def report_token_budget(self) -> dict[str, Any]:
        """Report token budget usage across artifacts and contexts."""
        registry = ArtifactRegistry(self.project_root)
        document = registry.load()
        artifacts = document.artifacts

        total_tokens = sum(a.token_estimate for a in artifacts)
        fresh = [a for a in artifacts if a.status == "fresh"]
        stale = [a for a in artifacts if a.status == "stale"]

        return {
            "total_artifacts": len(artifacts),
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "total_tokens": total_tokens,
            "avg_tokens_per_artifact": total_tokens // max(len(artifacts), 1),
            "fresh_tokens": sum(a.token_estimate for a in fresh),
            "stale_tokens": sum(a.token_estimate for a in stale),
        }

    @staticmethod
    def _extract_references(text: str) -> list[str]:
        """Extract artifact path references from lesson text."""
        import re
        return re.findall(r'[\w/.-]+\.(?:md|py|yaml|json|txt|toml)', text)
