"""`forge channel` — read-only status and release broadcast (FR-CH-002/003).

CLI layer only: parse args, call exactly one use-case method, render. The use
case is imported lazily, mirroring the other sub-apps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from forge_os.cli.commands._shared import console, resolve_project_root

channel_app = typer.Typer(help="Interact with Forge OS over channels.")


@channel_app.command("status")
def channel_status(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Show a read-only project status summary."""
    from forge_os.use_cases.channels import ChannelUseCases

    root = resolve_project_root(path)
    summary = ChannelUseCases(root).status_summary()
    console.print(f"[bold]Project[/bold] {summary['project_id']}")
    console.print(f"Stage: {summary['current_stage'] or 'none'}")
    console.print(f"Next: {summary['next_action']}")
    console.print(f"Stale artifacts: {summary['stale_artifacts']}")


@channel_app.command("broadcast")
def channel_broadcast(
    message: Annotated[str, typer.Argument(help="Message/release notes to broadcast.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Broadcast a message (e.g. release notes) over the channel."""
    from forge_os.use_cases.channels import ChannelUseCases

    root = resolve_project_root(path)
    ChannelUseCases(root).broadcast_release(message)
    console.print("[green]Broadcast sent.[/green]")


@channel_app.command("feedback")
def channel_feedback(
    text: Annotated[str, typer.Argument(help="Feedback text to queue for triage.")],
    sender: Annotated[str, typer.Option("--sender", "-s", help="Channel sender id.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Submit feedback over a channel (queued for Stage 10 triage)."""
    from forge_os.use_cases.channels import ChannelUseCases

    root = resolve_project_root(path)
    result = ChannelUseCases(root).submit_feedback(text, sender)
    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Feedback queued ({result['feedback_id']}).[/green]")


@channel_app.command("pair")
def channel_pair(
    sender: Annotated[str, typer.Option("--sender", "-s", help="Channel sender id.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Begin binding a channel sender to a Forge identity (returns a pairing code)."""
    from forge_os.use_cases.channels import ChannelUseCases

    root = resolve_project_root(path)
    result = ChannelUseCases(root).request_pairing(sender)
    console.print(f"Pairing code for [bold]{sender}[/bold]: {result['pairing_code']}")
    console.print("Confirm with: forge channel confirm --sender <s> --code <c> --identity <id>")


@channel_app.command("confirm")
def channel_confirm(
    sender: Annotated[str, typer.Option("--sender", "-s", help="Channel sender id.")],
    code: Annotated[str, typer.Option("--code", "-c", help="Pairing code from `pair`.")],
    identity: Annotated[
        str, typer.Option("--identity", "-i", help="Forge identity to bind to.")
    ],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """HITL-confirm a channel identity binding."""
    from forge_os.use_cases.channels import ChannelUseCases

    root = resolve_project_root(path)
    result = ChannelUseCases(root).confirm_pairing(sender, code, identity)
    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Bound {sender} -> {identity}.[/green]")
