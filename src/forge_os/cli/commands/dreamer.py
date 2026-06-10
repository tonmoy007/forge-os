"""Dreamer maintenance commands."""

from pathlib import Path
from typing import Annotated

import typer

from forge_os.cli.commands._shared import console, resolve_project_root
from forge_os.use_cases.dreamer import DreamerUseCases

dreamer_app = typer.Typer(help="Run Dreamer offline maintenance routines.")

PathOption = Annotated[
    Path | None,
    typer.Option("--path", "-p", help="Directory inside a Forge project."),
]


@dreamer_app.command("digest")
def dreamer_digest(
    path: PathOption = None,
    for_date: Annotated[
        str | None,
        typer.Option("--date", help="Digest date (YYYY-MM-DD); defaults to today."),
    ] = None,
) -> None:
    """Write the daily activity digest to pipeline/log/."""

    result = _use_cases(path).digest(for_date=for_date)
    _fail_on_error(result)
    if result["written"]:
        console.print(f"[green]Digest written:[/green] {result['path']}")
    else:
        console.print("[yellow]No activity recorded for that day; no digest written.[/yellow]")


@dreamer_app.command("scan")
def dreamer_scan(path: PathOption = None) -> None:
    """Scan reflections and approved lessons for recurrences and tensions."""

    result = _use_cases(path).scan()
    _fail_on_error(result)
    console.print(f"Reflections scanned: {result['reflections_scanned']}")
    console.print(f"Lessons proposed: {len(result['lessons_proposed'])}")
    tensions = result["tensions"]
    console.print(f"Tensions detected: {len(tensions)}")
    for tension in tensions:
        console.print(
            f"  [yellow]{tension['lesson_a']} <> {tension['lesson_b']}[/yellow] "
            f"({tension['reason']})"
        )


@dreamer_app.command("decay")
def dreamer_decay(path: PathOption = None) -> None:
    """Apply confidence decay to approved lessons and mark stale ones dormant."""

    result = _use_cases(path).decay()
    _fail_on_error(result)
    console.print(
        f"Examined: {result['examined']}  Decayed: {result['decayed']}  "
        f"Newly dormant: {result['newly_dormant']}"
    )
    for lesson_id in result["dormant_ids"]:
        console.print(f"  [yellow]dormant:[/yellow] {lesson_id}")


def _use_cases(path: Path | None) -> DreamerUseCases:
    try:
        return DreamerUseCases(resolve_project_root(path))
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _fail_on_error(result: dict[str, object]) -> None:
    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
