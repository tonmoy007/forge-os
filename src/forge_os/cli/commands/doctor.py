"""`forge doctor` — environment preflight diagnostic (FR-HD-006) + `--fix` (FR-HD-007).

Bare `forge doctor` is read-only. It reports whether the host/install (and,
inside a project, the project) is ready to run Forge, and exits non-zero when
any required check FAILs (install-level always; project-scoped — config
validity, `.forge` write access — when inside a project); advisory conditions
are WARN/INFO and never fatal. So it is scriptable in CI/setup.

`--fix` opts into guarded auto-remediation (FR-HD-007): it shows a dry-run plan,
confirms each repair, refuses to act in CI / no-TTY without `--yes`, and gates
re-init over an existing `.forge/` behind `--force`. Only `--fix` mutates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from forge_os.cli.commands._shared import console
from forge_os.schemas.doctor import (
    DoctorReport,
    DoctorStatus,
    FixReport,
    RemediationAction,
    RemediationOutcome,
)

doctor_app = typer.Typer(help="Diagnose whether this environment can run Forge OS.")

_ICONS = {
    DoctorStatus.PASS: "✅",
    DoctorStatus.WARN: "⚠️",
    DoctorStatus.FAIL: "❌",
    DoctorStatus.INFO: "ℹ️",
}


@doctor_app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory to diagnose (defaults to cwd)."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the report as JSON."),
    ] = False,
    fix: Annotated[
        bool,
        typer.Option("--fix", help="Repair the failing checks (the only mutating mode)."),
    ] = False,
    assume_yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Apply fixes without prompting (needed in CI/no-TTY)."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="With --fix, allow re-initializing over an existing .forge/."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="With --fix, show the repair plan without applying it."),
    ] = False,
) -> None:
    """Run environment + (if present) project preflight checks (`--fix` to remediate)."""

    if ctx.invoked_subcommand is not None:
        return

    if not fix and (assume_yes or force or dry_run):
        console.print("[red]--yes/--force/--dry-run only apply with --fix[/red]")
        raise typer.Exit(code=2)

    if fix:
        _run_fix(path, json_output=json_output, assume_yes=assume_yes, force=force, dry_run=dry_run)
        return

    from forge_os.use_cases.doctor import DoctorUseCases

    report = DoctorUseCases(path).run()

    if json_output:
        typer.echo(json.dumps(_as_payload(report), indent=2))
    else:
        _render(report)

    if not report.ok:
        raise typer.Exit(code=1)


def _as_payload(report: DoctorReport) -> dict[str, object]:
    return {
        "ok": report.ok,
        "counts": report.counts(),
        "checks": [check.model_dump() for check in report.checks],
    }


def _render(report: DoctorReport) -> None:
    console.print("[bold]Forge OS Doctor[/bold]")
    for check in report.checks:
        # check.detail/remedy carry dynamic text (adapter str(exc), pydantic
        # validation errors) that may contain `[...]` — escape so Rich renders
        # it literally instead of corrupting output or raising MarkupError.
        console.print(f"{_ICONS[check.status]} {escape(check.name)}: {escape(check.detail)}")
        if check.remedy and check.status is DoctorStatus.FAIL:
            console.print(f"   [dim]→ {escape(check.remedy)}[/dim]")

    counts = report.counts()
    summary = (
        f"{counts['pass']} passed, {counts['warn']} warned, "
        f"{counts['fail']} failed, {counts['info']} info"
    )
    if report.ok:
        console.print(f"[green]✓ Environment ready[/green] — {summary}")
    else:
        console.print(f"[red]✗ Environment not ready[/red] — {summary}")


# ── `--fix` guarded auto-remediation (FR-HD-007) ──────────────────────────────

_FIX_ICONS = {
    RemediationOutcome.APPLIED: "✅",
    RemediationOutcome.FAILED: "❌",
    RemediationOutcome.SKIPPED: "⏭️",
    RemediationOutcome.BLOCKED: "🔒",
}


def _stdin_is_tty() -> bool:
    """Whether stdin is an interactive terminal (the per-action confirm gate).

    A named seam (not an inline ``sys.stdin.isatty()``) so tests can force the
    interactive path — Typer's ``CliRunner`` always presents a non-TTY stdin.
    """
    return sys.stdin.isatty()


def _run_fix(
    path: Path | None,
    *,
    json_output: bool,
    assume_yes: bool,
    force: bool,
    dry_run: bool,
) -> None:
    from forge_os.use_cases.doctor import DoctorFixUseCases

    def _confirm(action: RemediationAction) -> bool:
        return typer.confirm(f"Apply: {action.description}?", default=False)

    report = DoctorFixUseCases(path).fix(
        dry_run=dry_run,
        assume_yes=assume_yes,
        force=force,
        interactive=_stdin_is_tty(),
        confirm=_confirm,
    )

    if json_output:
        typer.echo(json.dumps(_fix_payload(report), indent=2))
    else:
        _render_fix(report)

    raise typer.Exit(code=_fix_exit_code(report))


def _fix_exit_code(report: FixReport) -> int:
    """0 when the run succeeded; 1 when refused or a required check still FAILs."""
    if report.refused:
        return 1
    if report.dry_run:
        return 0  # a plan preview is a successful run
    if report.final_report is not None and not report.final_report.ok:
        return 1
    return 0 if report.ok else 1


def _fix_payload(report: FixReport) -> dict[str, object]:
    data = report.model_dump(mode="json")
    data["ok"] = report.ok
    data["applied_any"] = report.applied_any
    return data


def _render_fix(report: FixReport) -> None:
    console.print("[bold]Forge OS Doctor — repair[/bold]")

    if not report.planned:
        final = report.final_report
        if final is not None and not final.ok:
            console.print(
                "[red]✗ Nothing auto-fixable[/red] — some checks still fail; see `forge doctor`"
            )
        else:
            console.print("[green]✓ Nothing to repair.[/green]")
        return

    if report.refused:
        console.print(f"[yellow]Refused[/yellow] — {escape(report.refusal_reason or '')}")
        return

    if report.dry_run:
        console.print("[bold]Planned repairs[/bold] (dry run — nothing applied):")
        for action in report.planned:
            suffix = f"  [dim]({escape(action.command)})[/dim]" if action.command else ""
            console.print(f"  • {escape(action.description)}{suffix}")
        return

    for result in report.results:
        icon = _FIX_ICONS[result.outcome]
        console.print(f"{icon} {escape(result.action.description)} — {escape(result.detail)}")
        if result.recheck_status is not None:
            console.print(f"   [dim]re-check: {result.recheck_status.value}[/dim]")

    failed = [r for r in report.results if r.outcome is RemediationOutcome.FAILED]
    final = report.final_report
    if failed:
        console.print(f"[red]✗ {len(failed)} repair(s) failed[/red]")
    elif final is not None and final.ok:
        console.print("[green]✓ Environment ready[/green] after repairs")
    elif final is not None:
        console.print("[red]✗ Environment still not ready[/red] — some checks still fail")
