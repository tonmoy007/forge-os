"""Daemon lifecycle commands (P10.04)."""

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from forge_os.cli.commands._shared import console, resolve_project_root
from forge_os.use_cases.daemon import DaemonUseCases

daemon_app = typer.Typer(help="Manage the Forge OS background daemon.")

_PATH_OPTION = typer.Option("--path", "-p", help="Directory inside a Forge project.")


@daemon_app.command("start")
def daemon_start(
    path: Annotated[Path | None, _PATH_OPTION] = None,
) -> None:
    """Start the background daemon for the current project."""

    try:
        root = resolve_project_root(path)
        result = DaemonUseCases(root).start()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]Daemon started[/green] (pid {result['pid']}, id {result['daemon_id']})."
    )


@daemon_app.command("stop")
def daemon_stop(
    path: Annotated[Path | None, _PATH_OPTION] = None,
) -> None:
    """Stop the running background daemon."""

    try:
        root = resolve_project_root(path)
        result = DaemonUseCases(root).stop()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    if result["stopped"]:
        console.print("[green]Daemon stopped.[/green]")
    else:
        console.print("[yellow]No running daemon found.[/yellow]")


@daemon_app.command("status")
def daemon_status_command(
    path: Annotated[Path | None, _PATH_OPTION] = None,
) -> None:
    """Show daemon liveness, heartbeat, task runs, and alert count."""

    try:
        root = resolve_project_root(path)
        status = DaemonUseCases(root).status()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    table = Table(title="Forge Daemon Status")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Running", "[green]yes[/green]" if status["running"] else "[red]no[/red]")
    table.add_row("PID", str(status["pid"] or "-"))
    table.add_row("Started at", status["started_at"] or "-")
    table.add_row("Last heartbeat", status["last_heartbeat"] or "-")
    for name, task in status["tasks"].items():
        table.add_row(
            f"Task: {name}",
            f"runs={task['runs']} failures={task['failures']} "
            f"last={task['last_status'] or '-'}",
        )
    table.add_row("Alerts", str(len(status["alerts"])))
    table.add_row("Log", status["log_path"])
    if status["stale_state"]:
        table.add_row("Stale state", "[yellow]state file present but pid is dead[/yellow]")
    console.print(table)


@daemon_app.command("logs")
def daemon_logs(
    path: Annotated[Path | None, _PATH_OPTION] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Lines to show.")] = 50,
) -> None:
    """Show the tail of the daemon log."""

    try:
        root = resolve_project_root(path)
        lines = DaemonUseCases(root).logs(limit=limit)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    if not lines:
        console.print("[yellow]No daemon log entries.[/yellow]")
        return
    for line in lines:
        console.print(line, highlight=False)


@daemon_app.command("restart")
def daemon_restart(
    path: Annotated[Path | None, _PATH_OPTION] = None,
) -> None:
    """Restart the background daemon."""

    try:
        root = resolve_project_root(path)
        result = DaemonUseCases(root).restart()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(
        f"[green]Daemon restarted[/green] (pid {result['pid']}, id {result['daemon_id']})."
    )
