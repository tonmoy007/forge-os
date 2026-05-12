"""Memory and lesson health checker."""

from __future__ import annotations

from pathlib import Path

from forge_os.health.checker import HealthChecker, HealthResult
from forge_os.memory.lessons import LessonStore


class MemoryHealthChecker(HealthChecker):
    """Check lesson/memory subsystem health."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check(self) -> HealthResult:
        try:
            store = LessonStore(self.project_root)
            lessons = store.list()
        except Exception as exc:
            return HealthResult(
                healthy=False,
                message=f"Failed to load lessons: {exc}",
            )

        approved = sum(1 for le in lessons if le.status == "approved")
        pending = sum(1 for le in lessons if le.status == "pending")
        deprecated = sum(1 for le in lessons if le.status == "deprecated")

        details = {
            "total_lessons": len(lessons),
            "approved": approved,
            "pending": pending,
            "deprecated": deprecated,
        }

        recommendations: list[str] = []
        if pending > 0:
            msg = f"{pending} pending lessons. Use `forge lesson approve`."
            recommendations.append(msg)

        return HealthResult(
            healthy=True,
            message=f"{len(lessons)} lessons ({approved} approved, {pending} pending).",
            details=details,
            recommendations=recommendations,
        )
