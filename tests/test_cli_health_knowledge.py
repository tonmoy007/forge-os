"""Tests for `forge health knowledge` (FR-HD-002)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from forge_os.cli.commands.health import health_app
from forge_os.memory.lessons import LessonStore
from forge_os.project.scaffold import initialize_project

runner = CliRunner()


def _seeded_project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Knowledge", profile="standard")
    store = LessonStore(tmp_path)
    store.add("check ghost-artifact.md when refactoring")  # stale reference
    store.add("duplicate wording here")
    store.add("duplicate wording here")  # duplicate -> conflict
    return tmp_path


def test_reports_integrity_issues_and_budget(tmp_path: Path) -> None:
    result = runner.invoke(health_app, ["knowledge", "--path", str(_seeded_project(tmp_path))])
    assert result.exit_code == 1  # integrity issues found -> scriptable non-zero
    assert "stale reference" in result.output  # line label, not just the raw token
    assert "ghost-artifact.md" in result.output
    assert "missing_artifact" in result.output  # issue tag pinned
    assert "duplicate lesson" in result.output
    assert "Artifact Token Budget" in result.output


def test_clean_project_exits_zero(tmp_path: Path) -> None:
    initialize_project(tmp_path, project_name="Clean", profile="standard")
    result = runner.invoke(health_app, ["knowledge", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "No integrity issues found" in result.output


def test_json_output_is_parseable(tmp_path: Path) -> None:
    result = runner.invoke(
        health_app, ["knowledge", "--path", str(_seeded_project(tmp_path)), "--json"]
    )
    payload = json.loads(result.output)
    assert payload["integrity"]["issue_count"] >= 2
    assert "artifact_budget" in payload
    assert isinstance(payload["artifact_budget"]["total_artifacts"], int)


def test_registered_on_health_sub_app(tmp_path: Path) -> None:
    from forge_os.cli.main import app

    result = runner.invoke(app, ["health", "knowledge", "--path", str(_seeded_project(tmp_path))])
    assert result.exit_code == 1
    assert "Knowledge Integrity" in result.output


def test_missing_project_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(health_app, ["knowledge", "--path", str(empty)])
    assert result.exit_code == 1


def test_corrupt_lessons_store_reports_cleanly(tmp_path: Path) -> None:
    # A corrupt store must yield a clean error + exit 1, never a raw traceback
    # leaking internal source paths (error-handling/security rules).
    initialize_project(tmp_path, project_name="Corrupt", profile="standard")
    (tmp_path / ".forge" / "lessons.yaml").write_text("{[ not valid yaml", encoding="utf-8")
    result = runner.invoke(health_app, ["knowledge", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert result.output.strip()  # a clean message was printed


def test_render_escapes_markup_in_dynamic_fields(capsys) -> None:
    # Lesson ids come from a hand-editable lessons.yaml and can contain `[...]`;
    # the renderer must escape them so Rich prints them literally, not as markup.
    from forge_os.cli.commands.health import _render_knowledge

    zero_budget = {
        key: 0
        for key in (
            "total_artifacts",
            "fresh_count",
            "stale_count",
            "total_tokens",
            "avg_tokens_per_artifact",
            "fresh_tokens",
            "stale_tokens",
        )
    }
    _render_knowledge(
        [{"lesson_id": "[red]evil[/red]", "reference": "x.md", "issue": "missing_artifact"}],
        [],
        zero_budget,
        1,
    )
    out = capsys.readouterr().out
    assert "[red]" in out  # rendered literally, not consumed as markup
