"""Environment preflight checks for `forge doctor` (FR-HD-006).

Domain module: introspects the host install (Python runtime, virtualenv,
package install, core dependencies) and — when given a project root — the
project's config validity and `.forge/` write access.

Strict-layer note: this module is domain-pure. It imports only stdlib, the
`config` loader, and the `doctor` schemas. The *adapter-availability* check
reuses ``AdapterUseCases`` (the use-case layer) and therefore lives in
``use_cases/doctor.py`` — a domain module must never import upward from
``use_cases/``.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
import tempfile
from pathlib import Path

from forge_os.config.loader import ConfigError, load_config
from forge_os.schemas.doctor import DoctorCheck, DoctorStatus

# Minimum interpreter version, mirroring ``requires-python`` in pyproject.toml.
MIN_PYTHON: tuple[int, int] = (3, 11)

# Import names of the runtime dependencies *declared* in pyproject ``dependencies``
# (``pyyaml`` imports as ``yaml``). Only declared deps — never transitive ones such
# as ``click``, which Typer 0.26+ no longer requires (see L010).
CORE_DEPENDENCIES: tuple[str, ...] = ("pydantic", "yaml", "typer", "rich")


def _is_writable(directory: Path) -> bool:
    """Return True if a file can actually be created+removed under *directory*.

    A real write-probe rather than ``os.access`` so the answer reflects the
    effective permissions (ACLs, read-only mounts), not just the mode bits.
    """
    try:
        with tempfile.TemporaryFile(dir=directory):
            return True
    except OSError:
        return False


class EnvironmentDoctor:
    """Run install-level and (optionally) project-scoped preflight checks.

    *project_root* is injectable (``None`` for install-only checks) so tests can
    exercise both modes against ``tmp_path`` without touching the real home dir.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root

    # ── install-level checks (always valid, no project required) ──────────────

    def check_python_runtime(self) -> DoctorCheck:
        version = sys.version_info[:2]
        rendered = f"{version[0]}.{version[1]}"
        if version < MIN_PYTHON:
            return DoctorCheck(
                name="Python runtime",
                status=DoctorStatus.FAIL,
                detail=f"Python {rendered} is below the required {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
                remedy=f"Use Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+",
            )
        return DoctorCheck(
            name="Python runtime",
            status=DoctorStatus.PASS,
            detail=f"Python {rendered}",
        )

    def check_virtualenv(self) -> DoctorCheck:
        in_venv = sys.prefix != sys.base_prefix
        if in_venv:
            return DoctorCheck(
                name="Virtualenv",
                status=DoctorStatus.PASS,
                detail=f"active ({sys.prefix})",
            )
        return DoctorCheck(
            name="Virtualenv",
            status=DoctorStatus.WARN,
            detail="not running inside a virtualenv",
            remedy="Activate a virtualenv (e.g. `.venv`)",
        )

    def check_forge_install(self) -> DoctorCheck:
        try:
            version = importlib.metadata.version("forge-os")
        except importlib.metadata.PackageNotFoundError:
            return DoctorCheck(
                name="forge-os install",
                status=DoctorStatus.FAIL,
                detail="forge-os is not installed in this environment",
                remedy="`pip install -e .`",
            )
        return DoctorCheck(
            name="forge-os install",
            status=DoctorStatus.PASS,
            detail=f"forge-os {version}",
        )

    def check_core_dependencies(self) -> DoctorCheck:
        missing = [name for name in CORE_DEPENDENCIES if importlib.util.find_spec(name) is None]
        if missing:
            return DoctorCheck(
                name="Core dependencies",
                status=DoctorStatus.FAIL,
                detail=f"missing: {', '.join(missing)}",
                remedy="`pip install -e .[dev]`",
            )
        return DoctorCheck(
            name="Core dependencies",
            status=DoctorStatus.PASS,
            detail=f"all present ({', '.join(CORE_DEPENDENCIES)})",
        )

    def install_checks(self) -> list[DoctorCheck]:
        """The four install-level checks, always safe to run without a project."""
        return [
            self.check_python_runtime(),
            self.check_virtualenv(),
            self.check_forge_install(),
            self.check_core_dependencies(),
        ]

    # ── project-scoped checks (require self.project_root) ─────────────────────

    def check_config_valid(self) -> DoctorCheck:
        if self.project_root is None:
            return self._no_project("Config validity")
        config_path = self.project_root / ".forge" / "config.yaml"
        try:
            load_config(config_path)
        except ConfigError as exc:
            return DoctorCheck(
                name="Config validity",
                status=DoctorStatus.FAIL,
                detail=str(exc).splitlines()[0],
                remedy=f"Fix {config_path}",
            )
        return DoctorCheck(
            name="Config validity",
            status=DoctorStatus.PASS,
            detail="config.yaml loaded and validated",
        )

    def check_forge_writable(self) -> DoctorCheck:
        if self.project_root is None:
            return self._no_project(".forge writable")
        forge_path = self.project_root / ".forge"
        if _is_writable(forge_path):
            return DoctorCheck(
                name=".forge writable",
                status=DoctorStatus.PASS,
                detail=f"{forge_path} is writable",
            )
        return DoctorCheck(
            name=".forge writable",
            status=DoctorStatus.FAIL,
            detail=f"{forge_path} is not writable",
            remedy="Check directory permissions",
        )

    @staticmethod
    def _no_project(name: str) -> DoctorCheck:
        return DoctorCheck(
            name=name,
            status=DoctorStatus.INFO,
            detail="skipped — not in a Forge project",
        )
