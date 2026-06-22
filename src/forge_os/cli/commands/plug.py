"""`forge plug` — local extension management (FR-EXT-002).

CLI layer only: parse args, call exactly one use-case method, render. No domain
imports beyond the use case (loaded lazily, mirroring the other sub-apps).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from forge_os.cli.commands._shared import console, resolve_project_root

plug_app = typer.Typer(help="Manage Forge OS extensions (plugins).")


@plug_app.command("list")
def plug_list(
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """List installed extensions."""
    from forge_os.use_cases.extensions import ExtensionUseCases

    root = resolve_project_root(path)
    extensions = ExtensionUseCases(root).list_extensions()
    if not extensions:
        console.print("[yellow]No extensions installed.[/yellow]")
        return
    console.print("[bold]Installed extensions[/bold]")
    for ext in extensions:
        manifest = ext["manifest"]
        console.print(
            f"• {manifest['name']} {manifest['version']} "
            f"[{manifest['extension_point']}]"
        )


@plug_app.command("install")
def plug_install(
    source: Annotated[
        Path,
        typer.Argument(help="Path to an extension directory or extension.yaml."),
    ],
    allow_unsigned: Annotated[
        bool,
        typer.Option("--allow-unsigned", help="Permit installing an unsigned extension."),
    ] = False,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Install a local extension."""
    from forge_os.use_cases.extensions import ExtensionUseCases

    root = resolve_project_root(path)
    result = ExtensionUseCases(root).install(str(source), allow_unsigned=allow_unsigned)
    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    manifest = result["extension"]["manifest"]
    console.print(
        f"[green]Installed {manifest['name']} {manifest['version']}[/green]"
    )


@plug_app.command("remove")
def plug_remove(
    name: Annotated[str, typer.Argument(help="Name of the extension to remove.")],
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Directory inside a Forge project."),
    ] = None,
) -> None:
    """Remove an installed extension."""
    from forge_os.use_cases.extensions import ExtensionUseCases

    root = resolve_project_root(path)
    result = ExtensionUseCases(root).remove(name)
    if not result["success"]:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Removed {name}[/green]")
