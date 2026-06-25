"""Tests for DoctorFixUseCases — guarded auto-remediation (FR-HD-007).

The orchestration (dry-run, per-action confirm, CI/no-TTY guard, --force gate,
re-check) is exercised with a fake RemediationRunner so no host mutation or
network happens; a final integration test drives the real executor's
config-rewrite path on a tmp project (local only).
"""

from __future__ import annotations

from pathlib import Path

import forge_os.use_cases.doctor as doctor_uc
from forge_os.config.loader import load_config
from forge_os.health.remediation import CONFIG_REWRITE_ACTION
from forge_os.project.scaffold import initialize_project
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.schemas.doctor import (
    DoctorStatus,
    FixReport,
    RemediationAction,
    RemediationKind,
    RemediationOutcome,
    RemediationResult,
)
from forge_os.use_cases.doctor import DoctorFixUseCases


class FakeRunner:
    """Records calls; returns a fixed ok/fail without touching the OS."""

    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, bool]] = []

    def create_venv(self, target: Path) -> tuple[bool, str]:
        self.calls.append(("create_venv", False))
        return self.ok, "venv"

    def install_deps(self, target: Path) -> tuple[bool, str]:
        self.calls.append(("install_deps", False))
        return self.ok, "deps"

    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]:
        self.calls.append(("init_project", force))
        return self.ok, "init"

    def rebuild_config(self, root: Path) -> tuple[bool, str]:
        self.calls.append(("rebuild_config", False))
        return self.ok, "config"


def _force_plan(monkeypatch, actions: list[RemediationAction]) -> None:
    monkeypatch.setattr(
        doctor_uc, "build_remediation_plan", lambda report, *, target: list(actions)
    )


# INSTALL_DEPS is used for the "applies" tests because its re-check reads ambient
# state (deps are present in the test env and in Docker after `-e .[dev]`), so the
# outcome is APPLIED regardless of what the fake did — deterministic everywhere.
_DEPS_ACTION = RemediationAction(
    kind=RemediationKind.INSTALL_DEPS, check_name="Core dependencies", description="x"
)
_INIT_FORCE_ACTION = RemediationAction(
    kind=RemediationKind.INIT_PROJECT,
    check_name="Forge project",
    description="x",
    requires_force=True,
)
_VENV_ACTION = RemediationAction(
    kind=RemediationKind.CREATE_VENV, check_name="Virtualenv", description="x"
)


def _result(outcome: RemediationOutcome) -> RemediationResult:
    return RemediationResult(action=_DEPS_ACTION, outcome=outcome, detail="x")


class TestDryRun:
    def test_dry_run_plans_but_does_not_mutate(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(dry_run=True)
        assert [a.kind for a in report.planned] == [RemediationKind.INSTALL_DEPS]
        assert report.results == []
        assert report.final_report is None
        assert runner.calls == []


class TestConfirm:
    def test_confirm_yes_applies(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner(ok=True)
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(confirm=lambda a: True)
        assert runner.calls == [("install_deps", False)]
        assert report.results[0].outcome is RemediationOutcome.APPLIED
        assert report.results[0].recheck_status is not None
        assert report.final_report is not None

    def test_confirm_no_skips(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(confirm=lambda a: False)
        assert runner.calls == []
        assert report.results[0].outcome is RemediationOutcome.SKIPPED

    def test_assume_yes_bypasses_confirm(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner()
        # confirm would refuse, but assume_yes bypasses the prompt entirely
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(
            assume_yes=True, confirm=lambda a: False
        )
        assert runner.calls == [("install_deps", False)]
        assert report.results[0].outcome is RemediationOutcome.APPLIED


class TestApplyFailure:
    def test_runner_failure_reports_failed(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner(ok=False)
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(assume_yes=True)
        assert report.results[0].outcome is RemediationOutcome.FAILED
        assert report.results[0].recheck_status is None  # nothing re-checked when apply failed


class TestCIGuard:
    def test_non_interactive_without_yes_refuses(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(interactive=False)
        assert report.refused is True
        assert report.refusal_reason
        assert runner.calls == []
        assert report.final_report is None

    def test_non_interactive_with_yes_applies(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_DEPS_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(interactive=False, assume_yes=True)
        assert report.refused is False
        assert runner.calls == [("install_deps", False)]


class TestForceGate:
    def test_reinit_blocked_without_force(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_INIT_FORCE_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(assume_yes=True)
        assert report.results[0].outcome is RemediationOutcome.BLOCKED
        assert runner.calls == []  # the fix never ran

    def test_reinit_runs_with_force(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_INIT_FORCE_ACTION])
        runner = FakeRunner()
        DoctorFixUseCases(tmp_path, runner=runner).fix(assume_yes=True, force=True)
        assert runner.calls == [("init_project", True)]


class TestEmptyPlan:
    def test_no_actions_returns_clean(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(assume_yes=True)
        assert report.planned == []
        assert report.results == []
        assert runner.calls == []


class TestConfigRewriteIntegration:
    """Drives the REAL executor's config-rewrite path end to end (local, no network)."""

    def test_invalid_config_is_rebuilt_and_audited(self, tmp_path) -> None:
        initialize_project(tmp_path, project_name="Demo", profile="standard")
        config_path = tmp_path / ".forge" / "config.yaml"
        config_path.write_text("{{{ not yaml", encoding="utf-8")

        # Real executor (default). Approve only the config rewrite so the result is
        # deterministic regardless of venv/deps state on the host or in Docker.
        report = DoctorFixUseCases(tmp_path).fix(
            confirm=lambda a: a.kind is RemediationKind.REBUILD_CONFIG
        )

        rebuilds = [r for r in report.results if r.action.kind is RemediationKind.REBUILD_CONFIG]
        assert len(rebuilds) == 1
        assert rebuilds[0].outcome is RemediationOutcome.APPLIED
        assert rebuilds[0].recheck_status is not None
        load_config(config_path)  # now valid (must not raise)
        assert (tmp_path / ".forge" / "config.yaml.bak").exists()
        entries = SecurityAuditLog(tmp_path).read_all()
        assert any(e["action"] == CONFIG_REWRITE_ACTION for e in entries)
        assert report.final_report is not None


class TestSelectivity:
    def test_decline_skips_only_that_action(self, tmp_path, monkeypatch) -> None:
        # Two-action plan: decline venv, approve deps — proves the loop applies the
        # approved action and skips only the declined one (no abort-on-first-decline).
        _force_plan(monkeypatch, [_VENV_ACTION, _DEPS_ACTION])
        runner = FakeRunner()
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(
            confirm=lambda a: a.kind is RemediationKind.INSTALL_DEPS
        )
        outcomes = {r.action.kind: r.outcome for r in report.results}
        assert outcomes[RemediationKind.CREATE_VENV] is RemediationOutcome.SKIPPED
        assert outcomes[RemediationKind.INSTALL_DEPS] is RemediationOutcome.APPLIED
        assert runner.calls == [("install_deps", False)]  # only the approved one ran


class TestVenvRecheck:
    def test_recheck_passes_when_venv_artifact_created(self, tmp_path, monkeypatch) -> None:
        _force_plan(monkeypatch, [_VENV_ACTION])

        class VenvRunner(FakeRunner):
            def create_venv(self, target: Path) -> tuple[bool, str]:
                (target / ".venv").mkdir(parents=True, exist_ok=True)
                (target / ".venv" / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
                self.calls.append(("create_venv", False))
                return True, "made venv"

        report = DoctorFixUseCases(tmp_path, runner=VenvRunner()).fix(assume_yes=True)
        assert report.results[0].outcome is RemediationOutcome.APPLIED
        assert report.results[0].recheck_status is DoctorStatus.PASS

    def test_recheck_fails_when_no_artifact(self, tmp_path, monkeypatch) -> None:
        # Runner claims success but creates nothing → recheck verifies the artifact
        # and reports FAILED, not a false APPLIED off an inert check.
        _force_plan(monkeypatch, [_VENV_ACTION])
        runner = FakeRunner(ok=True)
        report = DoctorFixUseCases(tmp_path, runner=runner).fix(assume_yes=True)
        assert report.results[0].outcome is RemediationOutcome.FAILED
        assert report.results[0].recheck_status is DoctorStatus.FAIL


class TestFixReportProperties:
    def test_ok_false_when_refused(self) -> None:
        assert FixReport(refused=True).ok is False

    def test_ok_false_when_any_failed(self) -> None:
        report = FixReport(results=[_result(RemediationOutcome.FAILED)])
        assert report.ok is False

    def test_ok_true_when_applied_and_skipped(self) -> None:
        report = FixReport(
            results=[_result(RemediationOutcome.APPLIED), _result(RemediationOutcome.SKIPPED)]
        )
        assert report.ok is True

    def test_applied_any(self) -> None:
        assert FixReport(results=[_result(RemediationOutcome.SKIPPED)]).applied_any is False
        assert FixReport(results=[_result(RemediationOutcome.APPLIED)]).applied_any is True
