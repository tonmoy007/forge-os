"""Tests for LazyContextUseCases and the lazy context CLI sub-app (P10.15-19)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from forge_os.cli.commands.lazy_context import lazy_app
from forge_os.context.lazy import LazyContextError
from forge_os.memory.lessons import LessonStore
from forge_os.project.scaffold import initialize_project
from forge_os.use_cases.lazy_context import LazyContextUseCases

runner = CliRunner()


def write_skill(forge_dir: Path, name: str, *, status: str = "installed") -> Path:
    skills_dir = forge_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / f"{name}.yaml"
    record = {
        "name": name,
        "description": f"{name} skill",
        "status": status,
        "project_path": "/tmp/demo",
        "patterns": [],
    }
    _ = path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


def make_use_cases(tmp_path: Path) -> tuple[LazyContextUseCases, Path, Path]:
    project_root = tmp_path / "proj"
    project_root.mkdir(exist_ok=True)
    forge_dir = tmp_path / "forge"
    return LazyContextUseCases(project_root, forge_dir=forge_dir), project_root, forge_dir


def test_budget_returns_bundle_dict(tmp_path: Path) -> None:
    use_cases, project_root, forge_dir = make_use_cases(tmp_path)
    _ = write_skill(forge_dir, "alpha")
    _ = LessonStore(project_root).add("a lesson", confidence=0.4, status="approved")

    bundle = use_cases.budget("srs", token_budget=2000)

    assert bundle["stage_id"] == "srs"
    assert bundle["token_budget"] == 2000
    assert [entry["name"] for entry in bundle["skills_menu"]] == ["alpha"]
    assert len(bundle["lesson_index"]) == 1
    assert bundle["within_budget"] is True
    assert bundle["trimmed"] == []


def test_lazy_stats_returns_token_accounting(tmp_path: Path) -> None:
    use_cases, project_root, forge_dir = make_use_cases(tmp_path)
    _ = write_skill(forge_dir, "alpha")
    _ = LessonStore(project_root).add("verbose lesson " * 30, confidence=0.4, status="approved")

    stats = use_cases.lazy_stats("srs", token_budget=2000)

    assert stats["budget"] == 2000
    assert stats["eager_tokens"] > 0
    assert stats["lazy_tokens"] > 0
    assert stats["within_budget"] is True


def test_expand_returns_full_skill_record(tmp_path: Path) -> None:
    use_cases, _, forge_dir = make_use_cases(tmp_path)
    _ = write_skill(forge_dir, "alpha")

    record = use_cases.expand("alpha")

    assert record["name"] == "alpha"
    assert record["status"] == "installed"


def test_expand_unknown_skill_raises(tmp_path: Path) -> None:
    use_cases, _, _ = make_use_cases(tmp_path)

    with pytest.raises(LazyContextError, match="Unknown skill"):
        _ = use_cases.expand("ghost")


# ── CLI sub-app (cli/commands/lazy_context.py) ─────────────────────────────


def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_cli_budget_renders_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _isolated_home(tmp_path, monkeypatch)
    _ = write_skill(home / ".forge", "demo-skill")
    project_root = tmp_path / "proj"
    _ = initialize_project(project_root, project_name="Demo", profile="minimal")

    result = runner.invoke(
        lazy_app, ["budget", "--stage", "srs", "--path", str(project_root)]
    )

    assert result.exit_code == 0, result.output
    assert "Lazy Context Budget" in result.output
    assert "demo-skill" in result.output


def test_cli_lazy_stats_renders_savings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _isolated_home(tmp_path, monkeypatch)
    project_root = tmp_path / "proj"
    _ = initialize_project(project_root, project_name="Demo", profile="minimal")

    result = runner.invoke(
        lazy_app,
        ["lazy-stats", "--stage", "srs", "--budget", "1000", "--path", str(project_root)],
    )

    assert result.exit_code == 0, result.output
    assert "Lazy Context Stats" in result.output
    assert "Eager tokens" in result.output


def test_cli_budget_fails_outside_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _isolated_home(tmp_path, monkeypatch)
    outside = tmp_path / "empty"
    outside.mkdir()

    result = runner.invoke(lazy_app, ["budget", "--stage", "srs", "--path", str(outside)])

    assert result.exit_code == 1
