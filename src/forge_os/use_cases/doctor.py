"""Use case for `forge doctor` — environment preflight diagnostic (FR-HD-006).

Composes the domain ``EnvironmentDoctor`` (install + filesystem/config checks)
with the same-layer ``AdapterUseCases`` (adapter availability). Project
resolution is best-effort: outside a Forge project the install-level checks
still run and the project-scoped block degrades to a single INFO line. This use
case never raises — every failure mode is reported as a check.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from forge_os.health.doctor import EnvironmentDoctor
from forge_os.health.remediation import (
    RemediationExecutor,
    RemediationRunner,
    build_remediation_plan,
)
from forge_os.project.detect import ProjectNotFoundError, find_project_root, is_forge_project
from forge_os.schemas.doctor import (
    DoctorCheck,
    DoctorReport,
    DoctorStatus,
    FixReport,
    RemediationAction,
    RemediationKind,
    RemediationOutcome,
    RemediationResult,
)
from forge_os.use_cases.adapters import AdapterUseCases


class DoctorUseCases:
    """Assemble a :class:`DoctorReport` for the current environment."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root

    def run(self) -> DoctorReport:
        checks: list[DoctorCheck] = EnvironmentDoctor().install_checks()

        root = self._resolve_project_root()
        if root is None:
            checks.append(
                DoctorCheck(
                    name="Forge project",
                    status=DoctorStatus.INFO,
                    detail="skipped — not in a Forge project",
                    remedy="`forge init` to create one",
                )
            )
            return DoctorReport(checks=checks)

        project_doctor = EnvironmentDoctor(root)
        checks.append(
            DoctorCheck(
                name="Forge project",
                status=DoctorStatus.PASS,
                detail=f"detected at {root}",
            )
        )
        checks.append(project_doctor.check_config_valid())
        checks.append(project_doctor.check_forge_writable())
        checks.append(self._adapter_check(root))
        return DoctorReport(checks=checks)

    def _resolve_project_root(self) -> Path | None:
        # OSError covers PermissionError/NotADirectoryError from the parent walk
        # (and a deleted cwd) — the "never raises" contract means an unreadable
        # ancestor degrades to "no project", not an uncaught traceback.
        try:
            return find_project_root(self.project_root or Path.cwd())
        except (ProjectNotFoundError, OSError):
            return None

    @staticmethod
    def _adapter_check(root: Path) -> DoctorCheck:
        """Summarize adapter availability; INFO-only (an absent provider is not a failure)."""
        try:
            statuses = AdapterUseCases(root).status()
        except Exception as exc:  # noqa: BLE001 — degrade to INFO, never crash the report
            # AdapterUseCases.status() loads config; if that is broken the
            # config-validity check already fails — here we just skip cleanly.
            return DoctorCheck(
                name="Adapters",
                status=DoctorStatus.INFO,
                detail=f"skipped — {exc}".splitlines()[0],
            )
        available = [s.adapter_id for s in statuses if s.available]
        unavailable = [f"{s.adapter_id} ({s.reason})" for s in statuses if not s.available]
        detail = f"{len(available)} available: {', '.join(available) or 'none'}"
        if unavailable:
            detail += f"; {len(unavailable)} unavailable: {', '.join(unavailable)}"
        return DoctorCheck(name="Adapters", status=DoctorStatus.INFO, detail=detail)


class DoctorFixUseCases:
    """Guarded auto-remediation for `forge doctor --fix` (FR-HD-007).

    Wraps the read-only :class:`DoctorUseCases` with the mutating fix path: build
    a plan from the current report, guard it (dry-run, per-action confirm,
    CI/no-TTY refusal, `--force` for re-init), apply each approved repair through
    an injectable :class:`RemediationRunner`, then re-run each repaired check and
    take a final read-only report for the exit-code decision.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        runner: RemediationRunner | None = None,
    ) -> None:
        self.project_root = project_root
        self._runner: RemediationRunner = runner or RemediationExecutor()

    def fix(
        self,
        *,
        dry_run: bool = False,
        assume_yes: bool = False,
        force: bool = False,
        interactive: bool = True,
        confirm: Callable[[RemediationAction], bool] | None = None,
    ) -> FixReport:
        """Plan and (unless *dry_run*) apply the safe repairs for the current env.

        *confirm* is consulted per action when *assume_yes* is False; *interactive*
        is whether a TTY is attached (a CLI passes ``stdin.isatty()``). A
        non-interactive run without *assume_yes* refuses to mutate anything.
        """

        report = DoctorUseCases(self.project_root).run()
        target = (self.project_root or Path.cwd()).resolve()
        detected = self._detect_root(target)
        plan = build_remediation_plan(report, target=target)
        fix_report = FixReport(dry_run=dry_run, planned=plan)

        if dry_run or not plan:
            return fix_report

        # CI / no-TTY guard: refuse to mutate without an explicit `--yes`.
        if not interactive and not assume_yes:
            fix_report.refused = True
            fix_report.refusal_reason = (
                "non-interactive environment — re-run with --yes to apply fixes"
            )
            return fix_report

        for action in plan:
            fix_report.results.append(
                self._apply(
                    action,
                    target=target,
                    base=detected or target,
                    assume_yes=assume_yes,
                    force=force,
                    confirm=confirm,
                )
            )

        fix_report.final_report = DoctorUseCases(self.project_root).run()
        return fix_report

    def _apply(
        self,
        action: RemediationAction,
        *,
        target: Path,
        base: Path,
        assume_yes: bool,
        force: bool,
        confirm: Callable[[RemediationAction], bool] | None,
    ) -> RemediationResult:
        if action.requires_force and not force:
            return RemediationResult(
                action=action,
                outcome=RemediationOutcome.BLOCKED,
                detail="refusing to overwrite an existing .forge/ without --force",
            )

        if not assume_yes:
            approved = confirm(action) if confirm is not None else False
            if not approved:
                return RemediationResult(
                    action=action,
                    outcome=RemediationOutcome.SKIPPED,
                    detail="declined by operator",
                )

        ok, detail = self._run_action(action, target=target, base=base, force=force)
        if not ok:
            return RemediationResult(
                action=action, outcome=RemediationOutcome.FAILED, detail=detail
            )

        recheck = self._recheck(action, target=target, base=base)
        outcome = (
            RemediationOutcome.FAILED
            if recheck is DoctorStatus.FAIL
            else RemediationOutcome.APPLIED
        )
        return RemediationResult(
            action=action, outcome=outcome, detail=detail, recheck_status=recheck
        )

    def _run_action(
        self, action: RemediationAction, *, target: Path, base: Path, force: bool
    ) -> tuple[bool, str]:
        # venv/deps/init act on the pointed-at directory — the same `target` the
        # plan discloses (`target/.venv`), so the dry-run disclosure stays truthful
        # from any working directory.
        if action.kind is RemediationKind.CREATE_VENV:
            return self._runner.create_venv(target)
        if action.kind is RemediationKind.INSTALL_DEPS:
            return self._runner.install_deps(target)
        if action.kind is RemediationKind.INIT_PROJECT:
            return self._runner.init_project(target, force=force)
        # REBUILD_CONFIG operates on the detected project root (where `.forge/` lives).
        return self._runner.rebuild_config(base)

    @staticmethod
    def _recheck(action: RemediationAction, *, target: Path, base: Path) -> DoctorStatus:
        """Re-verify the repair and return a status reflecting whether it worked.

        INIT/CONFIG/DEPS re-run the corresponding FR-HD-006 check. CREATE_VENV is
        special: its FR-HD-006 check (`check_virtualenv`) is process-scoped and
        cannot observe a freshly-created venv (the running interpreter is still
        outside it), so re-running it would be inert — we verify the venv artifact
        (`pyvenv.cfg`), the thing the fix actually produces, instead.
        """

        importlib.invalidate_caches()  # so a freshly-installed dependency is visible
        if action.kind is RemediationKind.INIT_PROJECT:
            return DoctorStatus.PASS if is_forge_project(target) else DoctorStatus.FAIL
        if action.kind is RemediationKind.CREATE_VENV:
            created = (target / ".venv" / "pyvenv.cfg").is_file()
            return DoctorStatus.PASS if created else DoctorStatus.FAIL
        doctor = EnvironmentDoctor(base)
        rechecks = {
            RemediationKind.INSTALL_DEPS: doctor.check_core_dependencies,
            RemediationKind.REBUILD_CONFIG: doctor.check_config_valid,
        }
        return rechecks[action.kind]().status

    @staticmethod
    def _detect_root(target: Path) -> Path | None:
        try:
            return find_project_root(target)
        except (ProjectNotFoundError, OSError):
            return None
