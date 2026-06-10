"""Phase 10 lazy context builder (P10.15-19, FR-LCB-001..004).

Instead of injecting full skill records and lesson texts into agent context,
expose a one-line skill menu and a light low-confidence lesson index. Agents
expand entries on demand via `expand_skill`. A budget guard caps the lazy
share at 25% of the stage token budget and trims deterministically instead of
raising.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from forge_os.context.registry import estimate_tokens
from forge_os.context.skills_reader import SkillReader
from forge_os.memory.lessons import LessonStore, LessonStoreError
from forge_os.memory.models import Lesson
from forge_os.schemas.lazy_context import LazyContextBundle

log = logging.getLogger("forge.context.lazy")

# FR-LCB-004: menu + index may consume at most this share of the stage budget.
LAZY_BUDGET_SHARE = 0.25
SUMMARY_MAX_CHARS = 80
MENU_STATUSES = frozenset({"installed", "approved"})


class LazyContextError(RuntimeError):
    """Raised when lazy context cannot be assembled."""


class LazyContextBuilder:
    """Compose skill menus and lesson indexes within a deterministic token cap."""

    def __init__(self, project_root: Path, forge_dir: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.skill_reader = SkillReader(forge_dir=forge_dir)
        self.lesson_store = LessonStore(self.project_root)

    def skill_menu(self) -> list[dict[str, object]]:
        """FR-LCB-001: one-line menu of installed/approved skills, sorted by name."""
        menu = [
            {
                "name": str(record.get("name", "")),
                "description": _first_line(str(record.get("description", ""))),
            }
            for record in self.skill_reader.list_records()
            if record.get("status") in MENU_STATUSES
        ]
        return sorted(menu, key=lambda entry: entry["name"])

    def expand_skill(self, name: str) -> dict[str, object]:
        """FR-LCB-002: return the full record for one menu entry on demand."""
        record = self.skill_reader.get(name)
        if record is None:
            raise LazyContextError(f"Unknown skill `{name}`.")
        return record

    def lesson_index(
        self,
        *,
        max_confidence: float = 0.7,
        stage_id: str | None = None,
    ) -> list[dict[str, object]]:
        """FR-LCB-003: light index of approved lessons below *max_confidence*."""
        return [
            {
                "id": lesson.id,
                "summary": lesson.text[:SUMMARY_MAX_CHARS],
                "confidence": lesson.confidence,
                "tags": list(lesson.tags),
            }
            for lesson in self._low_confidence_lessons(
                stage_id=stage_id, max_confidence=max_confidence
            )
        ]

    def build(self, stage_id: str, *, token_budget: int = 2000) -> LazyContextBundle:
        """FR-LCB-004: compose menu + index, trimming over-budget entries.

        Never raises on over-budget: lesson entries are trimmed by ascending
        confidence first, then the alphabetical tail of the skill menu, and the
        trims are recorded on the bundle and logged.
        """
        if token_budget < 1:
            raise LazyContextError("Lazy context token budget must be positive.")
        menu = self.skill_menu()
        index = self.lesson_index(stage_id=stage_id)
        lazy_budget = max(1, int(token_budget * LAZY_BUDGET_SHARE))
        trimmed: list[str] = []

        def lazy_total() -> int:
            return sum(_entry_tokens(entry) for entry in menu + index)

        while lazy_total() > lazy_budget and index:
            victim = min(index, key=lambda entry: (entry["confidence"], entry["id"]))
            index.remove(victim)
            trimmed.append(f"lesson:{victim['id']}")
        while lazy_total() > lazy_budget and menu:
            victim = menu.pop()
            trimmed.append(f"skill:{victim['name']}")

        lazy_tokens = lazy_total()
        if trimmed:
            log.warning(
                "Lazy context for stage %s exceeded its %s-token cap; trimmed %s entries: %s",
                stage_id,
                lazy_budget,
                len(trimmed),
                ", ".join(trimmed),
            )
        return LazyContextBundle(
            stage_id=stage_id,
            skills_menu=menu,
            lesson_index=index,
            token_budget=token_budget,
            lazy_tokens=lazy_tokens,
            trimmed=trimmed,
            within_budget=lazy_tokens <= lazy_budget,
        )

    def stats(self, stage_id: str, *, token_budget: int = 2000) -> dict[str, object]:
        """P10.19: compare eager (full records/texts) vs lazy (menu/index) tokens."""
        bundle = self.build(stage_id, token_budget=token_budget)
        eager_skill_tokens = sum(
            _entry_tokens(record)
            for record in self.skill_reader.list_records()
            if record.get("status") in MENU_STATUSES
        )
        eager_lesson_tokens = sum(
            estimate_tokens(lesson.text)
            for lesson in self._low_confidence_lessons(stage_id=stage_id)
        )
        eager_tokens = eager_skill_tokens + eager_lesson_tokens
        lazy_tokens = bundle.lazy_tokens
        reduction_pct = (
            round((eager_tokens - lazy_tokens) / eager_tokens * 100, 2)
            if eager_tokens > 0
            else 0.0
        )
        return {
            "eager_tokens": eager_tokens,
            "lazy_tokens": lazy_tokens,
            "reduction_pct": reduction_pct,
            "budget": token_budget,
            "within_budget": bundle.within_budget,
        }

    def _low_confidence_lessons(
        self,
        *,
        stage_id: str | None,
        max_confidence: float = 0.7,
    ) -> list[Lesson]:
        try:
            lessons = self.lesson_store.list(status="approved", stage_id=stage_id)
        except LessonStoreError as exc:
            raise LazyContextError(f"Could not load lessons for lazy context: {exc}") from exc
        return [lesson for lesson in lessons if lesson.confidence < max_confidence]


def _first_line(text: str) -> str:
    stripped = text.strip()
    return stripped.splitlines()[0] if stripped else ""


def _entry_tokens(entry: dict[str, object]) -> int:
    # Same estimator as ContextPruner's registry snapshots, applied to the
    # serialized form the agent would actually receive.
    return estimate_tokens(json.dumps(entry, sort_keys=True, default=str))
