"""Tests for the environment preflight domain layer (FR-HD-006).

Covers ``EnvironmentDoctor`` (install + project-scoped checks) and the
``DoctorReport`` derived logic. Host-dependent introspection (python version,
venv, deps, writability) is forced via injection/monkeypatch so the tests are
deterministic (L001 isolation).
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

import pytest

from forge_os.health.doctor import CORE_DEPENDENCIES, EnvironmentDoctor
from forge_os.project.scaffold import initialize_project
from forge_os.schemas.doctor import DoctorCheck, DoctorReport, DoctorStatus


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


class TestInstallChecks:
    def test_install_checks_return_four_checks(self) -> None:
        checks = EnvironmentDoctor().install_checks()
        names = [c.name for c in checks]
        assert names == [
            "Python runtime",
            "Virtualenv",
            "forge-os install",
            "Core dependencies",
        ]

    def test_python_runtime_passes_on_supported_interpreter(self) -> None:
        check = EnvironmentDoctor().check_python_runtime()
        assert check.status is DoctorStatus.PASS

    def test_python_runtime_fails_below_minimum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("forge_os.health.doctor.MIN_PYTHON", (99, 0))
        check = EnvironmentDoctor().check_python_runtime()
        assert check.status is DoctorStatus.FAIL
        assert check.remedy is not None and "99.0" in check.remedy

    def test_virtualenv_warns_when_not_in_venv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("forge_os.health.doctor.sys.base_prefix", sys.prefix)
        check = EnvironmentDoctor().check_virtualenv()
        assert check.status is DoctorStatus.WARN
        assert check.remedy is not None

    def test_virtualenv_passes_when_in_venv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force prefix != base_prefix so the PASS branch is exercised regardless
        # of whether the test host itself runs inside a venv (Docker root does not).
        monkeypatch.setattr("forge_os.health.doctor.sys.base_prefix", sys.prefix + "_base")
        check = EnvironmentDoctor().check_virtualenv()
        assert check.status is DoctorStatus.PASS

    def test_forge_install_passes_when_distribution_present(self) -> None:
        check = EnvironmentDoctor().check_forge_install()
        assert check.status is DoctorStatus.PASS
        assert "forge-os" in check.detail

    def test_forge_install_fails_when_distribution_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(_name: str) -> str:
            raise importlib.metadata.PackageNotFoundError("forge-os")

        monkeypatch.setattr(importlib.metadata, "version", _raise)
        check = EnvironmentDoctor().check_forge_install()
        assert check.status is DoctorStatus.FAIL
        assert check.remedy == "`pip install -e .`"

    def test_core_dependencies_pass_when_all_present(self) -> None:
        check = EnvironmentDoctor().check_core_dependencies()
        assert check.status is DoctorStatus.PASS

    def test_core_dependencies_fail_when_one_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real = __import__("importlib.util", fromlist=["find_spec"]).find_spec

        def _fake(name: str, *args: object, **kwargs: object) -> object:
            return None if name == "pydantic" else real(name)

        monkeypatch.setattr("forge_os.health.doctor.importlib.util.find_spec", _fake)
        check = EnvironmentDoctor().check_core_dependencies()
        assert check.status is DoctorStatus.FAIL
        assert "pydantic" in check.detail
        assert "pydantic" in CORE_DEPENDENCIES


class TestProjectScopedChecks:
    def test_config_valid_passes_for_real_project(self, tmp_path: Path) -> None:
        check = EnvironmentDoctor(_project(tmp_path)).check_config_valid()
        assert check.status is DoctorStatus.PASS

    def test_config_valid_fails_for_broken_config(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / ".forge" / "config.yaml").write_text("{{{ not yaml", encoding="utf-8")
        check = EnvironmentDoctor(root).check_config_valid()
        assert check.status is DoctorStatus.FAIL
        assert check.remedy is not None

    def test_writable_passes_for_real_project(self, tmp_path: Path) -> None:
        check = EnvironmentDoctor(_project(tmp_path)).check_forge_writable()
        assert check.status is DoctorStatus.PASS

    def test_writable_fails_when_probe_reports_unwritable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("forge_os.health.doctor._is_writable", lambda _p: False)
        check = EnvironmentDoctor(_project(tmp_path)).check_forge_writable()
        assert check.status is DoctorStatus.FAIL

    def test_project_scoped_checks_skip_without_root(self) -> None:
        doctor = EnvironmentDoctor(None)
        for check in (doctor.check_config_valid(), doctor.check_forge_writable()):
            assert check.status is DoctorStatus.INFO
            assert "not in a Forge project" in check.detail


class TestDoctorReport:
    def test_ok_true_when_no_failures(self) -> None:
        report = DoctorReport(
            checks=[
                DoctorCheck(name="a", status=DoctorStatus.PASS, detail=""),
                DoctorCheck(name="b", status=DoctorStatus.WARN, detail=""),
                DoctorCheck(name="c", status=DoctorStatus.INFO, detail=""),
            ]
        )
        assert report.ok is True

    def test_ok_false_when_any_failure(self) -> None:
        report = DoctorReport(
            checks=[
                DoctorCheck(name="a", status=DoctorStatus.PASS, detail=""),
                DoctorCheck(name="b", status=DoctorStatus.FAIL, detail=""),
            ]
        )
        assert report.ok is False

    def test_counts_tally_every_status(self) -> None:
        report = DoctorReport(
            checks=[
                DoctorCheck(name="a", status=DoctorStatus.PASS, detail=""),
                DoctorCheck(name="b", status=DoctorStatus.PASS, detail=""),
                DoctorCheck(name="c", status=DoctorStatus.FAIL, detail=""),
            ]
        )
        assert report.counts() == {"pass": 2, "warn": 0, "fail": 1, "info": 0}
