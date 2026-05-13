"""Security commands — delegates to SecurityUseCases."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from forge_os.cli.commands._shared import console, resolve_project_status
from forge_os.core import StateError
from forge_os.project.detect import ProjectNotFoundError
from forge_os.schemas.config import ConfigError
from forge_os.use_cases import SecurityUseCases

security_app = typer.Typer(help="View security audit logs.")


@security_app.command("audit")
def security_audit(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of entries to show.")] = 20,
) -> None:
    """Show recent security audit log entries."""

    try:
        root, _config, _state = resolve_project_status(path)
    except (ProjectNotFoundError, ConfigError, StateError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    use_cases = SecurityUseCases(root)
    entries = use_cases.get_audit_entries(limit)
    if not entries:
        console.print("[yellow]No security audit entries found.[/yellow]")
        return

    table = Table(title=f"Security Audit Log (Last {len(entries)} entries)")
    table.add_column("Time", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Decision", style="magenta")
    table.add_column("Capability", style="yellow")
    for entry in entries:
        table.add_row(
            entry.get("timestamp", "")[:19].replace("T", " "),
            entry.get("action", ""),
            entry.get("decision", ""),
            entry.get("capability", ""),
        )
    console.print(table)