"""Use case for `forge doctor` — environment preflight diagnostic (FR-HD-006).

Composes the domain ``EnvironmentDoctor`` (install + filesystem/config checks)
with the same-layer ``AdapterUseCases`` (adapter availability). Project
resolution is best-effort: outside a Forge project the install-level checks
still run and the project-scoped block degrades to a single INFO line. This use
case never raises — every failure mode is reported as a check.
"""

from __future__ import annotations

from pathlib import Path

from forge_os.health.doctor import EnvironmentDoctor
from forge_os.project.detect import ProjectNotFoundError, find_project_root
from forge_os.schemas.doctor import DoctorCheck, DoctorReport, DoctorStatus
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
