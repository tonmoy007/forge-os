from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli_helpers import isolated_filesystem
from forge_os.agents.executor import run_stage_agent
from forge_os.cli.main import app
from forge_os.memory.lessons import LessonStore
from forge_os.memory.reflections import ReflectionStore
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state

runner = CliRunner()


def test_lesson_store_approval_and_deprecation(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    store = LessonStore(tmp_path)

    lesson = store.add(
        "Prefer deterministic checks before invoking adapters.",
        confidence=0.9,
        tags=["Quality", "quality", "Adapter"],
        stage_id="srs",
    )

    assert lesson.status == "pending"
    assert lesson.tags == ["quality", "adapter"]
    assert store.approved_for_context(stage_id="srs") == []

    approved = store.approve(lesson.id)
    assert approved.status == "approved"
    assert len(store.approved_for_context(stage_id="srs")) == 1

    deprecated = store.deprecate(lesson.id)
    assert deprecated.status == "deprecated"
    assert store.approved_for_context(stage_id="srs") == []


def test_stage_completion_records_reflection_and_pending_lesson(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")

    from forge_os.core import StateManager

    manager = StateManager.for_project(tmp_path)
    _ = manager.complete_stage("srs")

    reflections = ReflectionStore(tmp_path).list(stage_id="srs")
    lessons = LessonStore(tmp_path).list(status="pending", stage_id="srs")

    assert len(reflections) == 1
    assert reflections[0].event_type == "StageCompleted"
    assert reflections[0].metadata["lesson_extraction_status"] == "pending_approval"
    assert len(lessons) == 1
    assert lessons[0].source == "reflection"
    assert lessons[0].status == "pending"


def test_only_approved_high_confidence_lessons_enter_agent_context(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    store = LessonStore(tmp_path)
    pending = store.add(
        "Pending lessons must not enter context.",
        confidence=1.0,
        stage_id="srs",
        tags=["context"],
    )
    approved = store.add(
        "Approved lessons should enter context.",
        confidence=0.95,
        stage_id="srs",
        tags=["context"],
    )
    low_confidence = store.add(
        "Low confidence approved lessons should stay out.",
        confidence=0.3,
        stage_id="srs",
        tags=["context"],
    )
    _ = store.approve(approved.id)
    _ = store.approve(low_confidence.id)

    state = load_state(tmp_path)
    record = run_stage_agent(tmp_path, state, "srs")

    injected = record.metadata["approved_lessons"]
    injected_ids = {lesson["id"] for lesson in injected}
    assert approved.id in injected_ids
    assert pending.id not in injected_ids
    assert low_confidence.id not in injected_ids


def test_lesson_cli_lifecycle() -> None:
    with isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        add_result = runner.invoke(
            app,
            [
                "lesson",
                "add",
                "Prefer contract-first agent outputs.",
                "--confidence",
                "0.9",
                "--tag",
                "agents",
                "--stage",
                "srs",
            ],
        )
        lessons = yaml.safe_load(Path(".forge/lessons.yaml").read_text(encoding="utf-8"))[
            "lessons"
        ]
        lesson_id = lessons[0]["id"]
        approve_result = runner.invoke(app, ["lesson", "approve", lesson_id])
        list_result = runner.invoke(app, ["lesson", "list", "--status", "approved"])
        deprecate_result = runner.invoke(app, ["lesson", "deprecate", lesson_id])

        assert init_result.exit_code == 0, init_result.output
        assert add_result.exit_code == 0, add_result.output
        assert approve_result.exit_code == 0, approve_result.output
        assert list_result.exit_code == 0, list_result.output
        assert "approved" in list_result.output
        assert deprecate_result.exit_code == 0, deprecate_result.output
        updated = yaml.safe_load(Path(".forge/lessons.yaml").read_text(encoding="utf-8"))
        assert updated["lessons"][0]["status"] == "deprecated"


def test_reflection_cli_lists_stage_completion_reflections() -> None:
    with isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        _ = Path("SRS.md").write_text("# Requirements\n", encoding="utf-8")
        complete_result = runner.invoke(app, ["stage", "complete", "srs"])
        list_result = runner.invoke(app, ["reflection", "list", "--stage", "srs"])
        reflection_files = list(Path(".forge/reflections").glob("*.yaml"))
        reflection = yaml.safe_load(reflection_files[0].read_text(encoding="utf-8"))[
            "reflection"
        ]
        show_result = runner.invoke(app, ["reflection", "show", reflection["id"]])

        assert init_result.exit_code == 0, init_result.output
        assert complete_result.exit_code == 0, complete_result.output
        assert list_result.exit_code == 0, list_result.output
        assert "StageCompleted" in list_result.output
        assert show_result.exit_code == 0, show_result.output
        assert "lesson_extraction_status" in show_result.output


def test_agent_run_log_records_injected_lessons() -> None:
    with isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo"])
        add_result = runner.invoke(
            app,
            [
                "lesson",
                "add",
                "Always validate contract outputs.",
                "--confidence",
                "0.95",
                "--stage",
                "srs",
                "--approve",
            ],
        )
        run_result = runner.invoke(app, ["agent", "run"])
        record = json.loads(Path(".forge/agent-runs.jsonl").read_text(encoding="utf-8"))

        assert add_result.exit_code == 0, add_result.output
        assert run_result.exit_code == 0, run_result.output
        assert record["metadata"]["approved_lessons"][0]["text"] == (
            "Always validate contract outputs."
        )


def test_dormant_lessons_are_excluded_from_context(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson = store.add("Dormant lessons must stay out of context.", confidence=0.95)
    _ = store.approve(lesson.id)
    document = store.load()
    document.lessons[0].dormant = True
    store.save(document)

    assert store.approved_for_context() == []
    assert store.render_context() == []


def test_render_context_records_usage(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson = store.add("Usage must be recorded on injection.", confidence=0.95)
    _ = store.approve(lesson.id)

    first = store.render_context()
    second = store.render_context()

    assert [entry["id"] for entry in first] == [lesson.id]
    assert [entry["id"] for entry in second] == [lesson.id]
    refreshed = store.load().lessons[0]
    assert refreshed.use_count == 2
    assert refreshed.last_used_at is not None


def test_revive_clears_dormancy(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson = store.add("Dormant lessons remain available for revival.", confidence=0.95)
    _ = store.approve(lesson.id)
    document = store.load()
    document.lessons[0].dormant = True
    document.lessons[0].dormant_at = "2026-06-01T00:00:00Z"
    store.save(document)

    revived = store.revive(lesson.id)

    assert revived.dormant is False
    assert revived.dormant_at is None
    assert [item.id for item in store.approved_for_context()] == [lesson.id]


def test_lessons_yaml_without_usage_fields_loads_with_defaults(tmp_path: Path) -> None:
    store = LessonStore(tmp_path)
    lesson = store.add("Old store files must keep loading.", confidence=0.9)
    _ = store.approve(lesson.id)
    raw = yaml.safe_load(store.path.read_text(encoding="utf-8"))
    for field in ("last_used_at", "use_count", "dormant", "dormant_at"):
        del raw["lessons"][0][field]
    _ = store.path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    loaded = store.load().lessons[0]

    assert loaded.last_used_at is None
    assert loaded.use_count == 0
    assert loaded.dormant is False
    assert loaded.dormant_at is None
