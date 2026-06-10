"""Tests for the lazy context builder and its executor integration (P10.15-19)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from forge_os.context.lazy import LazyContextBuilder, LazyContextError
from forge_os.memory.lessons import LessonStore
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state
from forge_os.schemas.lazy_context import LazyContextBundle


def write_skill(
    forge_dir: Path,
    name: str,
    *,
    status: str = "installed",
    description: str | None = None,
) -> Path:
    skills_dir = forge_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / f"{name}.yaml"
    record = {
        "name": name,
        "description": description if description is not None else f"{name} skill",
        "status": status,
        "project_path": "/tmp/demo",
        "patterns": ["pattern-a"],
    }
    _ = path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


def make_builder(tmp_path: Path) -> tuple[LazyContextBuilder, Path, Path]:
    project_root = tmp_path / "proj"
    project_root.mkdir(exist_ok=True)
    forge_dir = tmp_path / "forge"
    return LazyContextBuilder(project_root, forge_dir=forge_dir), project_root, forge_dir


# ── Skill menu (P10.15 / FR-LCB-001) ───────────────────────────────────────


def test_skill_menu_includes_only_installed_and_approved_sorted(tmp_path: Path) -> None:
    builder, _, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "zeta", status="installed")
    _ = write_skill(forge_dir, "alpha", status="approved")
    _ = write_skill(forge_dir, "beta", status="proposed")

    menu = builder.skill_menu()

    assert [entry["name"] for entry in menu] == ["alpha", "zeta"]
    assert all(set(entry) == {"name", "description"} for entry in menu)


def test_skill_menu_uses_first_description_line_only(tmp_path: Path) -> None:
    builder, _, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha", description="first line\nsecond line")

    menu = builder.skill_menu()

    assert menu[0]["description"] == "first line"


# ── Skill expansion (P10.16 / FR-LCB-002) ──────────────────────────────────


def test_expand_skill_returns_full_record(tmp_path: Path) -> None:
    builder, _, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha", description="does alpha things")

    record = builder.expand_skill("alpha")

    assert record["description"] == "does alpha things"
    assert record["patterns"] == ["pattern-a"]


def test_expand_unknown_skill_raises_lazy_context_error(tmp_path: Path) -> None:
    builder, _, _ = make_builder(tmp_path)

    with pytest.raises(LazyContextError, match="Unknown skill"):
        _ = builder.expand_skill("ghost")


# ── Lesson index (P10.17 / FR-LCB-003) ─────────────────────────────────────


def test_lesson_index_includes_only_approved_below_max_confidence(tmp_path: Path) -> None:
    builder, project_root, _ = make_builder(tmp_path)
    store = LessonStore(project_root)
    low = store.add("low confidence lesson", confidence=0.5, status="approved")
    _ = store.add("high confidence lesson", confidence=0.9, status="approved")
    _ = store.add("boundary confidence lesson", confidence=0.7, status="approved")
    _ = store.add("pending lesson", confidence=0.2, status="pending")

    index = builder.lesson_index()

    assert [entry["id"] for entry in index] == [low.id]
    assert index[0]["confidence"] == 0.5
    assert index[0]["tags"] == []


def test_lesson_index_truncates_summary_to_80_chars(tmp_path: Path) -> None:
    builder, project_root, _ = make_builder(tmp_path)
    text = "x" * 200
    lesson = LessonStore(project_root).add(text, confidence=0.4, status="approved")

    index = builder.lesson_index()

    assert index[0]["id"] == lesson.id
    assert index[0]["summary"] == text[:80]
    assert len(index[0]["summary"]) == 80


def test_lesson_index_filters_by_stage(tmp_path: Path) -> None:
    builder, project_root, _ = make_builder(tmp_path)
    store = LessonStore(project_root)
    srs_lesson = store.add("srs lesson", confidence=0.4, status="approved", stage_id="srs")
    global_lesson = store.add("global lesson", confidence=0.4, status="approved")
    _ = store.add("build lesson", confidence=0.4, status="approved", stage_id="build")

    index = builder.lesson_index(stage_id="srs")

    assert {entry["id"] for entry in index} == {srs_lesson.id, global_lesson.id}


# ── Budget guard (P10.18 / FR-LCB-004) ─────────────────────────────────────


def test_build_within_budget_keeps_all_entries(tmp_path: Path) -> None:
    builder, project_root, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha")
    _ = LessonStore(project_root).add("short lesson", confidence=0.4, status="approved")

    bundle = builder.build("srs", token_budget=2000)

    assert isinstance(bundle, LazyContextBundle)
    assert [entry["name"] for entry in bundle.skills_menu] == ["alpha"]
    assert len(bundle.lesson_index) == 1
    assert bundle.trimmed == []
    assert bundle.within_budget is True
    assert 0 < bundle.lazy_tokens <= 500  # 25% cap of 2000


def test_build_trims_everything_deterministically_on_tiny_budget(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    builder, project_root, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha", status="approved")
    _ = write_skill(forge_dir, "zeta", status="installed")
    store = LessonStore(project_root)
    mid = store.add("mid lesson " * 10, confidence=0.4, status="approved")
    low = store.add("low lesson " * 10, confidence=0.2, status="approved")
    high = store.add("high lesson " * 10, confidence=0.6, status="approved")

    with caplog.at_level(logging.WARNING, logger="forge.context.lazy"):
        bundle = builder.build("srs", token_budget=4)  # cap: 1 token

    # Lessons trimmed first by ascending confidence, then the menu tail.
    assert bundle.trimmed == [
        f"lesson:{low.id}",
        f"lesson:{mid.id}",
        f"lesson:{high.id}",
        "skill:zeta",
        "skill:alpha",
    ]
    assert bundle.skills_menu == []
    assert bundle.lesson_index == []
    assert bundle.lazy_tokens == 0
    assert bundle.within_budget is True
    assert "trimmed 5 entries" in caplog.text


def test_build_trims_lowest_confidence_lesson_first(tmp_path: Path) -> None:
    builder, project_root, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha")
    store = LessonStore(project_root)
    low = store.add("low lesson " * 5, confidence=0.2, status="approved")
    _ = store.add("high lesson " * 5, confidence=0.6, status="approved")

    full = builder.build("srs", token_budget=2000)
    assert full.trimmed == []
    # Force at least one trim: shrink the cap just below the untrimmed total.
    bundle = builder.build("srs", token_budget=(full.lazy_tokens - 1) * 4)

    assert bundle.trimmed[0] == f"lesson:{low.id}"
    assert bundle.within_budget is True


def test_build_rejects_non_positive_budget(tmp_path: Path) -> None:
    builder, _, _ = make_builder(tmp_path)

    with pytest.raises(LazyContextError, match="must be positive"):
        _ = builder.build("srs", token_budget=0)


def test_build_wraps_lesson_store_errors(tmp_path: Path) -> None:
    builder, project_root, _ = make_builder(tmp_path)
    forge_meta = project_root / ".forge"
    forge_meta.mkdir(parents=True, exist_ok=True)
    _ = (forge_meta / "lessons.yaml").write_text("lessons: [unclosed", encoding="utf-8")

    with pytest.raises(LazyContextError, match="Could not load lessons"):
        _ = builder.build("srs")


# ── Stats (P10.19) ─────────────────────────────────────────────────────────


def test_stats_reports_eager_vs_lazy_reduction(tmp_path: Path) -> None:
    builder, project_root, forge_dir = make_builder(tmp_path)
    _ = write_skill(forge_dir, "alpha", description="d " * 200)
    _ = LessonStore(project_root).add("verbose lesson " * 50, confidence=0.4, status="approved")

    stats = builder.stats("srs", token_budget=2000)

    assert set(stats) == {
        "eager_tokens",
        "lazy_tokens",
        "reduction_pct",
        "budget",
        "within_budget",
    }
    assert stats["budget"] == 2000
    assert stats["within_budget"] is True
    assert stats["eager_tokens"] > stats["lazy_tokens"] > 0
    expected_pct = round(
        (stats["eager_tokens"] - stats["lazy_tokens"]) / stats["eager_tokens"] * 100, 2
    )
    assert stats["reduction_pct"] == expected_pct


def test_stats_with_no_records_reports_zero_reduction(tmp_path: Path) -> None:
    builder, _, _ = make_builder(tmp_path)

    stats = builder.stats("srs")

    assert stats["eager_tokens"] == 0
    assert stats["lazy_tokens"] == 0
    assert stats["reduction_pct"] == 0.0
    assert stats["within_budget"] is True


# ── Executor integration (P10.18 surgical extension) ───────────────────────


def _run_stage_capturing_context(project_root: Path) -> dict[str, object]:
    from forge_os.adapters.dummy import DummyAdapter
    from forge_os.agents.executor import run_stage_agent

    state = load_state(project_root)
    captured: dict[str, str] = {}
    original_spawn = DummyAdapter.spawn_agent

    def capturing_spawn(self, persona, context, tools):  # noqa: ANN001
        captured["context"] = context
        return original_spawn(self, persona, context, tools)

    with patch.object(DummyAdapter, "spawn_agent", capturing_spawn):
        _ = run_stage_agent(project_root, state, "srs")
    return json.loads(captured["context"])


def test_stage_context_includes_lazy_context_with_skill_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    _ = write_skill(home / ".forge", "demo-skill", status="installed")
    project_root = tmp_path / "proj"
    _ = initialize_project(project_root, project_name="Demo", profile="minimal")

    context = _run_stage_capturing_context(project_root)

    lazy = context["lazy_context"]
    assert [entry["name"] for entry in lazy["skills_menu"]] == ["demo-skill"]
    assert lazy["lesson_index"] == []
    assert lazy["token_budget"] == 2000
    assert lazy["within_budget"] is True
    assert "error" not in lazy


def test_stage_context_survives_broken_forge_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    home = tmp_path / "home"
    (home / ".forge").mkdir(parents=True)
    # `skills` as a regular file makes iterdir() raise NotADirectoryError (OSError).
    _ = (home / ".forge" / "skills").write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)
    project_root = tmp_path / "proj"
    _ = initialize_project(project_root, project_name="Demo", profile="minimal")

    with caplog.at_level(logging.WARNING, logger="forge.agents.executor"):
        context = _run_stage_capturing_context(project_root)

    lazy = context["lazy_context"]
    assert lazy["skills_menu"] == []
    assert lazy["lesson_index"] == []
    assert lazy["error"]
    assert "Lazy context build failed" in caplog.text
