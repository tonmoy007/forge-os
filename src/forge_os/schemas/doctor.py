"""Schemas for the `forge doctor` environment preflight diagnostic (FR-HD-006).

New schema file. Imports only stdlib + pydantic (schemas are pure data). No
existing schema/contract is modified — doctor is an additive, read-only
diagnostic surface. See ``plan/SCOPE-doctor-and-token-budget-cli.md``.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class DoctorStatus(StrEnum):
    """Outcome of a single preflight check.

    ``FAIL`` is the only status that makes ``forge doctor`` exit non-zero;
    ``WARN`` and ``INFO`` are advisory and never fail the command.
    """

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


class DoctorCheck(BaseModel):
    """One environment/project check and its outcome."""

    name: str
    status: DoctorStatus
    detail: str
    remedy: str | None = None


class DoctorReport(BaseModel):
    """The full set of checks produced by one `forge doctor` run."""

    checks: list[DoctorCheck] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no check failed (warnings/info are non-fatal)."""
        return not any(check.status is DoctorStatus.FAIL for check in self.checks)

    def counts(self) -> dict[str, int]:
        """Count of checks per status, keyed by the status string value."""
        tally = {status.value: 0 for status in DoctorStatus}
        for check in self.checks:
            tally[check.status.value] += 1
        return tally


# ── Guarded auto-remediation (FR-HD-007, `forge doctor --fix`) ─────────────────
#
# Additive, pure-data models for the guarded mutator. The remediation *logic*
# lives in ``health/remediation.py`` (domain) and ``use_cases/doctor.py``; these
# schemas only describe the plan and its outcomes. See
# ``plan/SCOPE-observability-cost-backlog.md`` §#3.


class RemediationKind(StrEnum):
    """The safe environment repairs `forge doctor --fix` can perform."""

    CREATE_VENV = "create_venv"
    INSTALL_DEPS = "install_deps"
    INIT_PROJECT = "init_project"
    REBUILD_CONFIG = "rebuild_config"


class RemediationOutcome(StrEnum):
    """Result of attempting (or withholding) one remediation."""

    APPLIED = "applied"  # ran and its re-check no longer FAILs
    FAILED = "failed"  # ran but the apply raised or the re-check still FAILs
    SKIPPED = "skipped"  # the operator declined this action
    BLOCKED = "blocked"  # needs `--force` (re-init over an existing `.forge/`) not given


class RemediationAction(BaseModel):
    """One planned repair targeting a single FR-HD-006 check."""

    kind: RemediationKind
    check_name: str  # the DoctorCheck.name this repairs
    description: str  # human-readable dry-run line
    # The command disclosed to the operator for shell-level fixes (venv/deps);
    # None for in-process fixes (init/config) that run no external command.
    command: str | None = None
    # True only when the fix would overwrite an existing `.forge/` (re-init),
    # which requires `--force`.
    requires_force: bool = False


class RemediationResult(BaseModel):
    """The outcome of one :class:`RemediationAction`, with its re-check status."""

    action: RemediationAction
    outcome: RemediationOutcome
    detail: str
    # Status of the corresponding FR-HD-006 check re-run after the fix; None when
    # the action was skipped/blocked (nothing applied, nothing to re-check).
    recheck_status: DoctorStatus | None = None


class FixReport(BaseModel):
    """The full result of a `forge doctor --fix` invocation."""

    dry_run: bool = False
    planned: list[RemediationAction] = Field(default_factory=list)
    results: list[RemediationResult] = Field(default_factory=list)
    # Set when a non-interactive environment withholds every action (no `--yes`).
    refused: bool = False
    refusal_reason: str | None = None
    # A fresh read-only report taken after all fixes were applied; None for a
    # dry run or a refusal (nothing changed, so the original report still holds).
    final_report: DoctorReport | None = None

    @property
    def applied_any(self) -> bool:
        """True if at least one action actually ran and re-checked clean."""
        return any(r.outcome is RemediationOutcome.APPLIED for r in self.results)

    @property
    def ok(self) -> bool:
        """True when nothing was refused and no applied fix FAILed.

        Note: the command's *exit code* derives from ``final_report.ok`` (are any
        required checks still failing), not this flag — a fix can succeed while a
        non-auto-fixable check (e.g. Python version) keeps the environment unready.
        """
        if self.refused:
            return False
        return not any(r.outcome is RemediationOutcome.FAILED for r in self.results)
