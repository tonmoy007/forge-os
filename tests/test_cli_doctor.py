"""Tests for the `forge doctor` CLI sub-app (FR-HD-006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge_os.cli.commands.doctor import doctor_app
from forge_os.project.scaffold import initialize_project
from forge_os.schemas.doctor import DoctorCheck, DoctorReport, DoctorStatus

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


def _patch_report(monkeypatch: pytest.MonkeyPatch, report: DoctorReport) -> None:
    monkeypatch.setattr(
        "forge_os.use_cases.doctor.DoctorUseCases.run", lambda self: report
    )


def test_exit_zero_for_healthy_project(tmp_path: Path) -> None:
    result = runner.invoke(doctor_app, ["--path", str(_project(tmp_path))])
    assert result.exit_code == 0
    assert "Forge OS Doctor" in result.output
    assert "Environment ready" in result.output


def test_runs_outside_a_project(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(doctor_app, ["--path", str(empty)])
    assert result.exit_code == 0
    assert "not in a Forge project" in result.output


def test_exit_nonzero_when_install_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = __import__("importlib.util", fromlist=["find_spec"]).find_spec

    def _fake(name: str, *args: object, **kwargs: object) -> object:
        return None if name == "pydantic" else real(name)

    monkeypatch.setattr("forge_os.health.doctor.importlib.util.find_spec", _fake)
    result = runner.invoke(doctor_app, ["--path", str(_project(tmp_path))])
    assert result.exit_code == 1
    assert "Environment not ready" in result.output


def test_json_output_is_parseable(tmp_path: Path) -> None:
    result = runner.invoke(doctor_app, ["--path", str(_project(tmp_path)), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["checks"]
    assert {"name", "status", "detail", "remedy"} <= set(payload["checks"][0])
    assert set(payload["counts"]) == {"pass", "warn", "fail", "info"}


def test_render_escapes_markup_in_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A detail carrying Rich-markup tokens (e.g. a pydantic error or adapter
    # str(exc)) must render literally, never be interpreted or raise MarkupError.
    report = DoctorReport(
        checks=[
            DoctorCheck(
                name="Adapters",
                status=DoctorStatus.INFO,
                detail="boom [red]x[/red] ]bad[",
            )
        ]
    )
    _patch_report(monkeypatch, report)
    result = runner.invoke(doctor_app, ["--path", str(_project(tmp_path))])
    assert result.exit_code == 0
    assert "[red]" in result.output  # rendered literally, not consumed as markup


def test_remedy_shown_for_fail_suppressed_for_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = DoctorReport(
        checks=[
            DoctorCheck(
                name="Bad", status=DoctorStatus.FAIL, detail="broke", remedy="do-fix-now"
            ),
            DoctorCheck(
                name="Soft", status=DoctorStatus.WARN, detail="meh", remedy="optional-fix"
            ),
        ]
    )
    _patch_report(monkeypatch, report)
    result = runner.invoke(doctor_app, ["--path", str(_project(tmp_path))])
    assert result.exit_code == 1  # a FAIL is present
    assert "do-fix-now" in result.output  # FAIL remedy shown
    assert "optional-fix" not in result.output  # WARN remedy suppressed


def test_registered_on_top_level_app(tmp_path: Path) -> None:
    # Exercises the cli/main.py add_typer registration (a name typo there would
    # leave doctor_app directly invokable but route `forge doctor` nowhere).
    from forge_os.cli.main import app

    result = runner.invoke(app, ["doctor", "--path", str(_project(tmp_path))])
    assert result.exit_code == 0
    assert "Forge OS Doctor" in result.output
