"""Health subsystem commands."""

from pathlib import Path
from typing import Annotated

import typer

from forge_os.cli.commands._shared import console, resolve_project_root, resolve_project_status
from forge_os.project.status import stale_artifact_count

health_app = typer.Typer(help="Check Forge OS subsystem health.")


@health_app.command("check")
def health_check(
    path: Annotated[Path | None, typer.Option("--path", "-p", help="Directory inside a Forge project.")] = None,
) -> None:
    """Run full system health check across all subsystems."""

    try:
        from forge_os.use_cases.health import HealthUseCases

        root = resolve_project_root(path)
        use_cases = HealthUseCases(root)
        report = use_cases.run_full_check()
    except ImportError:
        console.print("[yellow]Running basic health check (full health module not available).[/yellow]")
        _run_basic_health_check(path)
        return
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print("[bold]Forge OS Health Report[/bold]")
    for subsystem, result in report.items():
        status_icon = "✅" if result.get("healthy", False) else "❌"
        console.print(f"{status_icon} {subsystem}: {result.get('message', 'unknown')}")


def _run_basic_health_check(path: Path | None) -> None:
    """Basic health check when the full health module is unavailable."""
    try:
        root, config, state = resolve_project_status(path)
        console.print(f"✅ Config: loaded (profile={config.profile})")
        console.print(f"✅ State: {state.schema_version} (current stage={state.current_stage_id or 'none'})")
        stale = stale_artifact_count(root)
        console.print(f"{'✅' if stale == 0 else '⚠️'} Artifacts: {stale} stale")
    except Exception as exc:
        console.print(f"❌ Health check failed: {exc}")