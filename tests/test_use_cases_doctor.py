"""Tests for DoctorUseCases composition (FR-HD-006).

Verifies the use case composes install + project-scoped checks, reuses
``AdapterUseCases`` for adapter availability, degrades cleanly outside a
project, and never raises even when config is broken.
"""

from __future__ import annotations

from pathlib import Path

from forge_os.project.scaffold import initialize_project
from forge_os.schemas.doctor import DoctorStatus
from forge_os.use_cases.doctor import DoctorUseCases


def _project(tmp_path: Path) -> Path:
    initialize_project(tmp_path, project_name="Demo", profile="standard")
    return tmp_path


def _by_name(report) -> dict[str, object]:
    return {c.name: c for c in report.checks}


class TestInProject:
    def test_report_includes_install_and_project_checks(self, tmp_path: Path) -> None:
        report = DoctorUseCases(_project(tmp_path)).run()
        names = _by_name(report)
        assert {
            "Python runtime",
            "forge-os install",
            "Forge project",
            "Config validity",
            ".forge writable",
            "Adapters",
        } <= set(names)
        assert report.ok is True

    def test_forge_project_check_passes(self, tmp_path: Path) -> None:
        report = DoctorUseCases(_project(tmp_path)).run()
        assert _by_name(report)["Forge project"].status is DoctorStatus.PASS

    def test_adapter_check_reuses_adapter_status(self, tmp_path: Path) -> None:
        # dummy is always available — its presence proves AdapterUseCases.status()
        # actually ran (reuse, not a re-implemented probe).
        report = DoctorUseCases(_project(tmp_path)).run()
        adapters = _by_name(report)["Adapters"]
        assert adapters.status is DoctorStatus.INFO
        assert "dummy" in adapters.detail


class TestOutsideProject:
    def test_degrades_to_single_info_without_project(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        report = DoctorUseCases(empty).run()
        names = _by_name(report)
        # install checks still present
        assert "Python runtime" in names
        # project block collapses to one INFO, no config/adapter checks
        assert names["Forge project"].status is DoctorStatus.INFO
        assert "not in a Forge project" in names["Forge project"].detail
        assert "Config validity" not in names
        assert "Adapters" not in names
        assert report.ok is True


class TestNeverRaises:
    def test_traversal_oserror_degrades_to_info(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # find_project_root walks parents calling Path.is_file(); an unreadable
        # ancestor raises PermissionError (OSError). The "never raises" contract
        # requires degrading to the project-skipped INFO, not crashing.
        def _boom(_start: Path) -> Path:
            raise PermissionError("denied")

        monkeypatch.setattr("forge_os.use_cases.doctor.find_project_root", _boom)
        report = DoctorUseCases(tmp_path).run()  # must not raise
        names = _by_name(report)
        assert names["Forge project"].status is DoctorStatus.INFO
        assert "Config validity" not in names
        assert report.ok is True


class TestBrokenConfig:
    def test_config_failure_does_not_raise_and_fails_report(self, tmp_path: Path) -> None:
        root = _project(tmp_path)
        (root / ".forge" / "config.yaml").write_text("{{{ not yaml", encoding="utf-8")
        report = DoctorUseCases(root).run()  # must not raise
        names = _by_name(report)
        assert names["Config validity"].status is DoctorStatus.FAIL
        assert report.ok is False
        # adapter probe also reads config; it degrades to INFO rather than crashing
        assert names["Adapters"].status is DoctorStatus.INFO
