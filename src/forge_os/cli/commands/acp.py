"""ACP (Agent Client Protocol) commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from forge_os.cli.commands._shared import resolve_project_root

console = Console()

acp_app = typer.Typer(help="Discover and manage ACP-compatible agents.")

_ACP_NOT_INSTALLED = (
    "[yellow]ACP support is not installed. "
    "Install with: pip install forge-os[acp][/yellow]"
)


@acp_app.command("discover")
def acp_discover(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Fetch and list ACP agents available in the official registry."""

    try:
        from forge_os.use_cases.acp import ACPUseCases

        root = resolve_project_root(path)
        use_cases = ACPUseCases(root)
        agents = use_cases.discover_agents()
    except ImportError:
        console.print(_ACP_NOT_INSTALLED)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not agents:
        console.print(
            "[yellow]No ACP agents found in registry. "
            "Check network connectivity.[/yellow]"
        )
        return

    table = Table(title=f"ACP Registry Agents ({len(agents)} found)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Version", no_wrap=True)
    table.add_column("License")
    table.add_column("Distributions")
    table.add_column("Description")
    for agent in agents:
        table.add_row(
            agent.get("id", ""),
            agent.get("name", ""),
            agent.get("version", ""),
            agent.get("license", ""),
            ", ".join(agent.get("distribution_types", [])),
            agent.get("description", "")[:60],
        )
    console.print(table)


@acp_app.command("list")
def acp_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List locally installed ACP agents."""

    try:
        from forge_os.use_cases.acp import ACPUseCases

        root = resolve_project_root(path)
        use_cases = ACPUseCases(root)
        agents = use_cases.list_installed_agents()
    except ImportError:
        console.print(_ACP_NOT_INSTALLED)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not agents:
        console.print(
            "[yellow]No ACP agents installed. "
            "Run `forge acp install <agent-id>` first.[/yellow]"
        )
        return

    table = Table(title=f"Installed ACP Agents ({len(agents)})")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Install Path")
    for agent in agents:
        table.add_row(
            agent.get("id", ""),
            agent.get("name", ""),
            agent.get("install_path", ""),
        )
    console.print(table)


@acp_app.command("install")
def acp_install(
    agent_id: Annotated[str, typer.Argument(help="ACP agent ID from the registry.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    distribution: Annotated[
        str | None,
        typer.Option("--distribution", "-d", help="Distribution method: binary, npx, or uvx."),
    ] = None,
) -> None:
    """Install an ACP agent from the registry."""

    try:
        from forge_os.use_cases.acp import ACPUseCases

        root = resolve_project_root(path)
        use_cases = ACPUseCases(root)
        install_path = use_cases.install_agent(agent_id, distribution_method=distribution)
        console.print(f"[green]Installed {agent_id} to:[/green] {install_path}")
    except ImportError:
        console.print(_ACP_NOT_INSTALLED)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]Failed to install {agent_id}:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@acp_app.command("sessions")
def acp_sessions(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
    agent_id: Annotated[
        str | None,
        typer.Option("--agent", help="Filter sessions by agent id."),
    ] = None,
) -> None:
    """List active ACP sessions."""

    try:
        from forge_os.use_cases.acp import ACPUseCases

        root = resolve_project_root(path)
        use_cases = ACPUseCases(root)
        sessions = use_cases.list_sessions(agent_id=agent_id)
    except ImportError:
        console.print(_ACP_NOT_INSTALLED)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not sessions:
        console.print("[yellow]No active ACP sessions found.[/yellow]")
        return

    table = Table(title=f"ACP Sessions ({len(sessions)})")
    table.add_column("Session ID", style="cyan")
    table.add_column("Agent ID")
    table.add_column("Title")
    for session in sessions:
        table.add_row(
            session.get("id", ""),
            session.get("agent_id", ""),
            session.get("title", ""),
        )
    console.print(table)


@acp_app.command("close-session")
def acp_close_session(
    session_id: Annotated[str, typer.Argument(help="ACP session ID to close.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Close an active ACP session."""

    try:
        from forge_os.use_cases.acp import ACPUseCases

        root = resolve_project_root(path)
        use_cases = ACPUseCases(root)
        use_cases.close_session(session_id)
        console.print(f"[green]Closed session:[/green] {session_id}")
    except ImportError:
        console.print(_ACP_NOT_INSTALLED)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        console.print(f"[red]Failed to close session {session_id}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
