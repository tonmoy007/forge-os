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
