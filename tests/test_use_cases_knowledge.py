"""Tests for KnowledgeUseCases (FR-HD-002 integrity scans + artifact budget).

These methods were previously CLI-invisible and untested; `forge health
knowledge` now surfaces them, so they get direct coverage here.
"""

from __future__ import annotations

from pathlib import Path

from forge_os.context.registry import ArtifactRegistry
from forge_os.memory.lessons import LessonStore
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.knowledge import KnowledgeUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Knowledge", profile="standard")
    return tmp_path


class TestScanLessonReferences:
    def test_flags_missing_artifact_reference(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        LessonStore(root).add("remember to update missing-thing.md before release")
        issues = KnowledgeUseCases(root).scan_lesson_references()
        assert any(
            i["reference"] == "missing-thing.md" and i["issue"] == "missing_artifact"
            for i in issues
        )

    def test_no_issue_when_no_file_references(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        LessonStore(root).add("a plain lesson mentioning no files at all")
        assert KnowledgeUseCases(root).scan_lesson_references() == []


class TestScanLessonConflicts:
    def test_flags_duplicate_lessons(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        store = LessonStore(root)
        store.add("exactly the same wording")
        store.add("exactly the same wording")
        conflicts = KnowledgeUseCases(root).scan_lesson_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["issue"] == "duplicate_lesson"

    def test_no_conflict_for_distinct_lessons(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        store = LessonStore(root)
        store.add("the first unique lesson")
        store.add("the second different lesson")
        assert KnowledgeUseCases(root).scan_lesson_conflicts() == []


class TestReportTokenBudget:
    def test_empty_project_has_full_schema(self, tmp_path: Path) -> None:
        budget = KnowledgeUseCases(_project(tmp_path)).report_token_budget()
        assert set(budget) == {
            "total_artifacts",
            "fresh_count",
            "stale_count",
            "total_tokens",
            "avg_tokens_per_artifact",
            "fresh_tokens",
            "stale_tokens",
        }
        assert all(isinstance(v, int) for v in budget.values())

    def test_counts_registered_artifact_tokens(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        before = KnowledgeUseCases(root).report_token_budget()["total_artifacts"]
        (root / "doc.md").write_text("word " * 200, encoding="utf-8")
        ArtifactRegistry(root).register("doc.md")
        after = KnowledgeUseCases(root).report_token_budget()
        assert after["total_artifacts"] == before + 1
        assert after["total_tokens"] > 0
