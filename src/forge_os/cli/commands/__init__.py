"""Forge OS CLI commands — Clean Code Architecture.

Each sub-module exposes a Typer sub-app (e.g. stage_app, gate_app).
Import and register with the root app in main.py.

Command rule: every command delegates to the use_cases layer.
CLI code handles only parsing, output formatting, and error translation.
"""

from forge_os.cli.commands._shared import (
    console,
    resolve_project_root,
    resolve_project_status,
    state_manager_for,
)

__all__ = [
    "console",
    "resolve_project_root",
    "resolve_project_status",
    "state_manager_for",
]