"""Forge backtrack commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from forge_os.cli.commands._shared import (
    console,
    resolve_project_status,
)
from forge_os.core import StateError
from forge_os.project.detect import ProjectNotFoundError
from forge_os.schemas.config import ConfigError
from forge_os.use_cases import BacktrackUseCases

backtrack_app = typer.Typer(help="Manage backtrack tickets and rework planning.")


@backtrack_app.command("list")
def backtrack_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List all backtrack tickets."""

    try:
        root, _config, _state = resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = BacktrackUseCases(root)
    tickets = use_cases.list_tickets()
    if not tickets:
        console.print("[yellow]No backtrack tickets found.[/yellow]")
        return

    table = Table(title="Backtrack Tickets")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Target Stage", style="green")
    table.add_column("Reason")
    table.add_column("Created", style="dim")
    for ticket in tickets:
        reason = ticket.reason
        if len(reason) > 50:
            reason = reason[:50] + "..."
        table.add_row(
            ticket.ticket_id,
            ticket.status.value,
            ticket.target_stage_id,
            reason,
            ticket.created_at[:19].replace("T", " "),
        )
    console.print(table)


@backtrack_app.command("plan")
def backtrack_plan(
    ticket_id: Annotated[str, typer.Argument(help="Backtrack ticket ID.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show the rework plan for a backtrack ticket."""

    try:
        root, _config, _state = resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = BacktrackUseCases(root)
    ticket = use_cases.get_ticket_plan(ticket_id)
    if not ticket:
        console.print(f"[red]Ticket {ticket_id} not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Backtrack Ticket: {ticket.ticket_id}[/bold]")
    console.print(f"Status: {ticket.status.value}")
    console.print(f"Reason: {ticket.reason}")
    console.print(f"Target Stage: {ticket.target_stage_id}")
    console.print(f"Source Stage: {ticket.source_stage_id}")
    console.print(f"Affected Artifacts ({len(ticket.affected_artifacts)}):")
    for artifact in ticket.affected_artifacts:
        console.print(f"  • {artifact}")


@backtrack_app.command("approve")
def backtrack_approve(
    ticket_id: Annotated[str, typer.Argument(help="Backtrack ticket ID.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Approve a backtrack ticket for execution."""

    try:
        root, _config, _state = resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = BacktrackUseCases(root)
    if use_cases.approve_ticket(ticket_id):
        console.print(f"[green]Ticket {ticket_id} approved.[/green]")
    else:
        console.print(f"[red]Failed to approve ticket {ticket_id}.[/red]")
        raise typer.Exit(code=1)


@backtrack_app.command("run")
def backtrack_run(
    ticket_id: Annotated[str, typer.Argument(help="Backtrack ticket ID.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Execute the rework plan for an approved backtrack ticket."""

    try:
        root, _config, _state = resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = BacktrackUseCases(root)
    if use_cases.run_rework(ticket_id):
        console.print(f"[green]Rework started for {ticket_id}. Artifacts marked stale.[/green]")
    else:
        console.print(
            f"[red]Failed to run rework for {ticket_id}. "
            "Ensure the ticket is approved.[/red]"
        )
        raise typer.Exit(code=1)