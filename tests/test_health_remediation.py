"""Tests for the FR-HD-007 remediation domain (`forge doctor --fix`).

Covers the plan builder (non-PASS checks → safe repairs) and the real
RemediationExecutor's local fixes (init, config rebuild + backup + audit) plus
its subprocess wrapper. No network: subprocess execution is exercised only
through trivial in-process commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from forge_os.config.loader import load_config
from forge_os.health.remediation import (
    CONFIG_REWRITE_ACTION,
    RemediationExecutor,
    build_remediation_plan,
)
from forge_os.project.detect import is_forge_project
from forge_os.project.scaffold import initialize_project
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.schemas.doctor import (
    DoctorCheck,
    DoctorReport,
    DoctorStatus,
    RemediationKind,
)


def _report(**statuses: DoctorStatus) -> DoctorReport:
    return DoctorReport(
        checks=[
            DoctorCheck(name=name, status=status, detail="x")
            for name, status in statuses.items()
        ]
    )


def _plan(target: Path, **statuses: DoctorStatus) -> list:
    return build_remediation_plan(_report(**statuses), target=target)


class TestBuildPlan:
    def test_venv_warn_plans_create_venv(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path, **{"Virtualenv": DoctorStatus.WARN})
        assert [a.kind for a in plan] == [RemediationKind.CREATE_VENV]

    def test_passing_venv_plans_nothing(self, tmp_path: Path) -> None:
        assert _plan(tmp_path, **{"Virtualenv": DoctorStatus.PASS}) == []

    def test_missing_deps_plans_install(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path, **{"Core dependencies": DoctorStatus.FAIL})
        assert [a.kind for a in plan] == [RemediationKind.INSTALL_DEPS]

    def test_forge_install_fail_also_plans_install(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path, **{"forge-os install": DoctorStatus.FAIL})
        assert [a.kind for a in plan] == [RemediationKind.INSTALL_DEPS]

    def test_no_project_plans_init_without_force(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path, **{"Forge project": DoctorStatus.INFO})
        assert len(plan) == 1
        assert plan[0].kind is RemediationKind.INIT_PROJECT
        assert plan[0].requires_force is False

    def test_no_project_but_existing_forge_requires_force(self, tmp_path: Path) -> None:
        (tmp_path / ".forge").mkdir()
        plan = _plan(tmp_path, **{"Forge project": DoctorStatus.INFO})
        assert plan[0].requires_force is True

    def test_invalid_config_plans_rebuild(self, tmp_path: Path) -> None:
        plan = _plan(tmp_path, **{"Config validity": DoctorStatus.FAIL})
        assert [a.kind for a in plan] == [RemediationKind.REBUILD_CONFIG]

    # Negative guards: a healthy check plans nothing (clause 5 "fires ONLY when invalid").
    def test_valid_config_plans_no_rebuild(self, tmp_path: Path) -> None:
        assert _plan(tmp_path, **{"Config validity": DoctorStatus.PASS}) == []

    def test_present_deps_plan_nothing(self, tmp_path: Path) -> None:
        assert _plan(tmp_path, **{"Core dependencies": DoctorStatus.PASS}) == []

    def test_existing_project_plans_no_init(self, tmp_path: Path) -> None:
        assert _plan(tmp_path, **{"Forge project": DoctorStatus.PASS}) == []


class TestInitProject:
    def test_init_creates_project(self, tmp_path: Path) -> None:
        ok, _ = RemediationExecutor().init_project(tmp_path, force=False)
        assert ok is True
        assert is_forge_project(tmp_path)

    def test_init_over_existing_forge_fails_without_force(self, tmp_path: Path) -> None:
        (tmp_path / ".forge").mkdir()
        ok, detail = RemediationExecutor().init_project(tmp_path, force=False)
        assert ok is False
        assert "already exists" in detail.lower() or "--force" in detail

    def test_init_over_existing_forge_succeeds_with_force(self, tmp_path: Path) -> None:
        (tmp_path / ".forge").mkdir()
        ok, _ = RemediationExecutor().init_project(tmp_path, force=True)
        assert ok is True
        assert is_forge_project(tmp_path)


class TestRebuildConfig:
    def test_rebuild_restores_valid_config_with_backup_and_audit(self, tmp_path: Path) -> None:
        initialize_project(tmp_path, project_name="Demo", profile="standard")
        config_path = tmp_path / ".forge" / "config.yaml"
        config_path.write_text("{{{ not yaml", encoding="utf-8")

        ok, _ = RemediationExecutor().rebuild_config(tmp_path)

        assert ok is True
        load_config(config_path)  # rebuilt config loads cleanly (must not raise)
        backup = tmp_path / ".forge" / "config.yaml.bak"
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "{{{ not yaml"  # invalid file preserved
        # the rewrite is audited (FR-HD-007 correction b)
        entries = SecurityAuditLog(tmp_path).read_all()
        rewrite = [e for e in entries if e["action"] == CONFIG_REWRITE_ACTION]
        assert len(rewrite) == 1
        assert rewrite[0]["decision"] == "allowed"

    def test_rebuild_does_not_clobber_existing_backup(self, tmp_path: Path) -> None:
        initialize_project(tmp_path, project_name="Demo", profile="standard")
        config_path = tmp_path / ".forge" / "config.yaml"
        existing_bak = tmp_path / ".forge" / "config.yaml.bak"
        existing_bak.write_text("PRIOR BACKUP", encoding="utf-8")
        config_path.write_text("{{{ not yaml", encoding="utf-8")

        ok, _ = RemediationExecutor().rebuild_config(tmp_path)

        assert ok is True
        # the pre-existing backup is untouched; the invalid file takes the next free name
        assert existing_bak.read_text(encoding="utf-8") == "PRIOR BACKUP"
        next_bak = tmp_path / ".forge" / "config.yaml.bak.1"
        assert next_bak.read_text(encoding="utf-8") == "{{{ not yaml"
        load_config(config_path)  # rebuilt config is valid


class TestExecutorArgv:
    """Pin the subprocess argv/cwd the FakeRunner cannot prove (no real venv/pip)."""

    @staticmethod
    def _record(monkeypatch) -> dict:
        calls: dict = {}

        def fake_run(cmd, **kwargs):
            calls["cmd"] = cmd
            calls["cwd"] = kwargs.get("cwd")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr("forge_os.health.remediation.subprocess.run", fake_run)
        return calls

    def test_create_venv_argv(self, tmp_path: Path, monkeypatch) -> None:
        calls = self._record(monkeypatch)
        ok, _ = RemediationExecutor().create_venv(tmp_path)
        assert ok is True
        assert calls["cmd"] == [sys.executable, "-m", "venv", str(tmp_path / ".venv")]
        assert calls["cwd"] is None

    def test_install_deps_argv_and_cwd(self, tmp_path: Path, monkeypatch) -> None:
        calls = self._record(monkeypatch)
        ok, _ = RemediationExecutor().install_deps(tmp_path)
        assert ok is True
        assert calls["cmd"] == [sys.executable, "-m", "pip", "install", "-e", ".[dev]"]
        assert calls["cwd"] == str(tmp_path)


class TestRunWrapper:
    def test_run_success(self) -> None:
        ok, _ = RemediationExecutor()._run([sys.executable, "-c", "pass"])
        assert ok is True

    def test_run_nonzero_exit_fails(self) -> None:
        ok, detail = RemediationExecutor()._run([sys.executable, "-c", "import sys; sys.exit(3)"])
        assert ok is False
        assert "failed" in detail

    def test_run_missing_binary_fails_cleanly(self) -> None:
        ok, detail = RemediationExecutor()._run(["forge-no-such-binary-xyz"])
        assert ok is False
        assert "could not run" in detail
