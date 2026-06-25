"""Guarded environment remediation for `forge doctor --fix` (FR-HD-007).

Domain module with two responsibilities:

* :func:`build_remediation_plan` — map a read-only :class:`DoctorReport`'s
  non-PASS checks to the safe repairs `forge doctor --fix` knows how to perform.
* :class:`RemediationExecutor` — the side-effecting primitives that actually
  perform those repairs (create a virtualenv, install dependencies, scaffold a
  project, rebuild an invalid config). Every side effect is funnelled through
  the :class:`RemediationRunner` protocol so the use case (and tests) can inject
  a fake and exercise the guard/confirm/audit logic without mutating the host or
  reaching the network.

Pure domain: imports stdlib, project scaffold/audit, and the doctor schemas;
never imports ``use_cases``/``cli``. See
``plan/SCOPE-observability-cost-backlog.md`` §#3.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

import yaml

from forge_os.project.scaffold import (
    ProjectAlreadyInitializedError,
    _build_config,
    initialize_project,
)
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.schemas.doctor import (
    DoctorReport,
    DoctorStatus,
    RemediationAction,
    RemediationKind,
)
from forge_os.schemas.security import SecurityAuditEntry, SecurityDecision

# DoctorCheck.name values the planner keys on (kept in one place so a rename of a
# doctor check surfaces here rather than silently dropping a remediation).
_VENV_CHECK = "Virtualenv"
_DEPS_CHECK = "Core dependencies"
_INSTALL_CHECK = "forge-os install"
_PROJECT_CHECK = "Forge project"
_CONFIG_CHECK = "Config validity"

# The audited action name for the invalid-config rewrite (FR-HD-007 correction b).
CONFIG_REWRITE_ACTION = "doctor_autofix_config_rewrite"


def build_remediation_plan(report: DoctorReport, *, target: Path) -> list[RemediationAction]:
    """Map non-PASS FR-HD-006 checks to the safe repairs available for them.

    *target* is the directory a project would be initialized into (the resolved
    project root when inside one, else the path/cwd the operator pointed at).
    """

    by_name = {check.name: check for check in report.checks}
    actions: list[RemediationAction] = []
    interpreter = Path(sys.executable).name

    venv = by_name.get(_VENV_CHECK)
    if venv is not None and venv.status is DoctorStatus.WARN:
        actions.append(
            RemediationAction(
                kind=RemediationKind.CREATE_VENV,
                check_name=_VENV_CHECK,
                description=f"Create a virtualenv at {target / '.venv'}",
                command=f"{interpreter} -m venv .venv",
            )
        )

    deps = by_name.get(_DEPS_CHECK)
    install = by_name.get(_INSTALL_CHECK)
    if (deps is not None and deps.status is DoctorStatus.FAIL) or (
        install is not None and install.status is DoctorStatus.FAIL
    ):
        actions.append(
            RemediationAction(
                kind=RemediationKind.INSTALL_DEPS,
                check_name=_DEPS_CHECK,
                description="Install the project and its dependencies",
                command=f"{interpreter} -m pip install -e '.[dev]'",
            )
        )

    project = by_name.get(_PROJECT_CHECK)
    if project is not None and project.status is DoctorStatus.INFO:
        actions.append(
            RemediationAction(
                kind=RemediationKind.INIT_PROJECT,
                check_name=_PROJECT_CHECK,
                description=f"Initialize a Forge project at {target}",
                # A bare `.forge/` that is not yet a valid project still blocks
                # init; overwriting it is the `--force`-gated case (correction c).
                requires_force=(target / ".forge").exists(),
            )
        )

    config = by_name.get(_CONFIG_CHECK)
    if config is not None and config.status is DoctorStatus.FAIL:
        actions.append(
            RemediationAction(
                kind=RemediationKind.REBUILD_CONFIG,
                check_name=_CONFIG_CHECK,
                description="Rebuild .forge/config.yaml from defaults (backs up the invalid file)",
            )
        )

    return actions


class RemediationRunner(Protocol):
    """The side-effecting operations a remediation may perform.

    Injected into the use case so tests can substitute a fake. Each method
    returns ``(ok, detail)`` — ``ok`` False means the repair itself failed.
    """

    def create_venv(self, target: Path) -> tuple[bool, str]: ...
    def install_deps(self, target: Path) -> tuple[bool, str]: ...
    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]: ...
    def rebuild_config(self, root: Path) -> tuple[bool, str]: ...


class RemediationExecutor:
    """Real :class:`RemediationRunner` — performs the environment mutations.

    Subprocess fixes (venv/deps) shell out to the *current* interpreter; the
    in-process fixes reuse ``project.scaffold``. Isolated here so nothing else in
    the fix path touches the OS directly.
    """

    def create_venv(self, target: Path) -> tuple[bool, str]:
        return self._run([sys.executable, "-m", "venv", str(target / ".venv")])

    def install_deps(self, target: Path) -> tuple[bool, str]:
        return self._run([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], cwd=target)

    def init_project(self, target: Path, *, force: bool) -> tuple[bool, str]:
        try:
            root = initialize_project(target, project_name=target.name, overwrite=force)
        except ProjectAlreadyInitializedError as exc:
            return False, str(exc)
        return True, f"initialized Forge project at {root}"

    def rebuild_config(self, root: Path) -> tuple[bool, str]:
        forge_path = root / ".forge"
        forge_path.mkdir(parents=True, exist_ok=True)
        config_path = forge_path / "config.yaml"
        # Non-destructive: preserve the invalid file as `.bak`, never clobbering an
        # existing backup (a prior run's, or the operator's) — fall back to
        # `.bak.1`, `.bak.2`, … until a free name is found.
        backup = config_path.with_name(config_path.name + ".bak")
        suffix = 1
        while backup.exists():
            backup = config_path.with_name(f"{config_path.name}.bak.{suffix}")
            suffix += 1
        if config_path.exists():
            config_path.replace(backup)
        config = _build_config(root.name, "minimal")
        config_path.write_text(
            yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        self._audit_config_rewrite(root, config_path)
        return True, f"rebuilt {config_path} from defaults (backup at {backup})"

    @staticmethod
    def _audit_config_rewrite(root: Path, config_path: Path) -> None:
        SecurityAuditLog(root).log(
            SecurityAuditEntry(
                audit_id=f"AUD-{int(time.time() * 1000)}",
                actor={"type": "doctor_autofix"},
                action=CONFIG_REWRITE_ACTION,
                target=str(config_path),
                decision=SecurityDecision.ALLOWED,
                reason="rebuilt invalid config.yaml from defaults",
            )
        )

    @staticmethod
    def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
            )
        except OSError as exc:  # command missing / not executable
            return False, f"could not run {cmd[0]}: {exc}"
        if proc.returncode == 0:
            return True, f"`{' '.join(cmd)}` succeeded"
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        why = tail[-1] if tail else f"exit {proc.returncode}"
        return False, f"`{' '.join(cmd)}` failed: {why}"
