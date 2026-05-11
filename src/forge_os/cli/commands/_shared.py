"""Shared utilities for all Forge OS CLI commands.

This module is the single import point for every command sub-module.
It exposes helpers for project resolution, state management, and the
shared Rich console — enforcing that CLI code never mixes business logic
with I/O.

All functions here are thin wrappers around the core/domain layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from forge_os.core import StateManager

# ─── Shared Console ───────────────────────────────────────────────────────────

console = Console()

# ─── Project Resolution ───────────────────────────────────────────────────────


def resolve_project_root(path: Path | None) -> Path:
    """Return the Forge project root, searching upward from *path*."""
    from forge_os.project.detect import find_project_root

    return find_project_root((path or Path.cwd()).resolve())


def resolve_project_status(
    path: Path | None,
) -> tuple[Path, object, object]:
    """Return (root, config, state) for a project at *path*.

    Raises StateError / ConfigError / ProjectNotFoundError on failure.
    """
    from forge_os.project.status import read_project_status

    return read_project_status((path or Path.cwd()).resolve())


def state_manager_for(path: Path | None) -> StateManager:
    """Return a StateManager bound to the project at *path*."""
    from forge_os.core import StateManager

    root = resolve_project_root(path)
    return StateManager.for_project(root)