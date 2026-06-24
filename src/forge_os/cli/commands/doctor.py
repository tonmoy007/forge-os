"""`forge doctor` — environment preflight diagnostic (FR-HD-006).

Read-only. Reports whether the host/install (and, inside a project, the
project) is ready to run Forge. Exits non-zero when any required check FAILs
(install-level always; project-scoped — config validity, `.forge` write access
— when inside a project); advisory conditions are WARN/INFO and never fatal. So
it is scriptable in CI/setup.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape

from forge_os.cli.commands._shared import console
from forge_os.schemas.doctor import DoctorReport, DoctorStatus

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
) -> None:
    """Run environment + (if present) project preflight checks."""

    if ctx.invoked_subcommand is not None:
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
