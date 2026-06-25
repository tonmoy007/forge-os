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


# ── `--fix` (FR-HD-007) ───────────────────────────────────────────────────────


class _LocalFakeRunner:
    """Cheap local effects only — no real venv/pip — so CLI apply tests are fast."""

    def create_venv(self, target: Path) -> tuple[bool, str]:
        (target / ".venv").mkdir(parents=True, exist_ok=True)
        (target / ".venv" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
        return True, "venv created"

    def install_deps(self, target: Path) -> tuple[bool, str]:
        return True, "deps ok"

    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]:
        initialize_project(target, project_name=target.name, overwrite=force)
        return True, "initialized"

    def rebuild_config(self, root: Path) -> tuple[bool, str]:
        return True, "config ok"


class _NoOpRunner(_LocalFakeRunner):
    """Claims success but creates nothing — every re-check then FAILs."""

    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]:
        return True, "claimed-but-did-nothing"

    def create_venv(self, target: Path) -> tuple[bool, str]:
        return True, "claimed-but-did-nothing"


class _MarkupRunner(_LocalFakeRunner):
    """Returns a detail carrying Rich-markup tokens, to test render escaping."""

    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]:
        initialize_project(target, project_name=target.name, overwrite=force)
        return True, "done [red]x[/red] ]bad["


def _inject_runner(monkeypatch: pytest.MonkeyPatch, cls: type) -> None:
    monkeypatch.setattr("forge_os.use_cases.doctor.RemediationExecutor", cls)


def _empty(tmp_path: Path) -> Path:
    target = tmp_path / "env"
    target.mkdir()
    return target


@pytest.mark.parametrize("flag", ["--yes", "--force", "--dry-run"])
def test_fix_flags_require_fix(flag: str) -> None:
    # Each mutating-only flag, given without --fix, is a usage error (exit 2).
    result = runner.invoke(doctor_app, [flag])
    assert result.exit_code == 2
    assert "only apply with --fix" in result.output


def test_fix_dry_run_plans_but_mutates_nothing(tmp_path: Path) -> None:
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target), "--fix", "--dry-run"])
    assert result.exit_code == 0
    assert "Planned repairs" in result.output
    assert not (target / ".forge").exists()  # dry run created nothing


def test_fix_non_interactive_refuses_without_yes(tmp_path: Path) -> None:
    # Under CliRunner stdin is not a TTY, so --fix without --yes must refuse.
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target), "--fix"])
    assert result.exit_code == 1
    assert "Refused" in result.output
    assert not (target / ".forge").exists()


def test_fix_yes_applies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _inject_runner(monkeypatch, _LocalFakeRunner)
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target), "--fix", "--yes"])
    assert result.exit_code == 0
    assert (target / ".forge").exists()  # init applied
    assert "re-check:" in result.output  # per-result re-check line rendered
    assert "Environment ready" in result.output


def test_fix_reports_failure_with_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _inject_runner(monkeypatch, _NoOpRunner)
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target), "--fix", "--yes"])
    assert result.exit_code == 1
    assert "repair(s) failed" in result.output


def test_fix_dry_run_json(tmp_path: Path) -> None:
    target = _empty(tmp_path)
    result = runner.invoke(
        doctor_app, ["--path", str(target), "--fix", "--dry-run", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["planned"]  # at least the init action
    assert "ok" in payload and "applied_any" in payload


def test_fix_apply_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _inject_runner(monkeypatch, _LocalFakeRunner)
    target = _empty(tmp_path)
    result = runner.invoke(
        doctor_app, ["--path", str(target), "--fix", "--yes", "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["applied_any"] is True
    assert any(r["outcome"] == "applied" for r in payload["results"])
    assert payload["final_report"] is not None


def test_fix_render_escapes_markup_in_detail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A repair detail carrying Rich-markup tokens (e.g. a subprocess stderr tail)
    # must render literally, never be interpreted or raise MarkupError.
    _inject_runner(monkeypatch, _MarkupRunner)
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target), "--fix", "--yes"])
    assert result.exit_code == 0
    assert "[red]" in result.output  # rendered literally, not consumed as markup


def test_fix_nothing_to_repair_on_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = DoctorReport(
        checks=[DoctorCheck(name="Python runtime", status=DoctorStatus.PASS, detail="3.12")]
    )
    _patch_report(monkeypatch, report)
    result = runner.invoke(doctor_app, ["--path", str(tmp_path), "--fix", "--yes"])
    assert result.exit_code == 0
    assert "Nothing to repair" in result.output


def test_fix_exits_nonzero_when_unfixable_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A required FAIL with no remediation (e.g. an unsupported Python) yields an
    # empty plan — but --fix must still exit non-zero (clause 8) and say so.
    report = DoctorReport(
        checks=[
            DoctorCheck(
                name="Python runtime", status=DoctorStatus.FAIL, detail="3.10", remedy="3.11+"
            )
        ]
    )
    _patch_report(monkeypatch, report)
    result = runner.invoke(doctor_app, ["--path", str(tmp_path), "--fix", "--yes"])
    assert result.exit_code == 1
    assert "auto-fixable" in result.output


def test_bare_doctor_does_not_mutate_repairable_dir(tmp_path: Path) -> None:
    # Clause 1: the read-only path never repairs, even on a dir --fix would init.
    target = _empty(tmp_path)
    result = runner.invoke(doctor_app, ["--path", str(target)])
    assert result.exit_code == 0
    assert not (target / ".forge").exists()
