"""Forge project root detection."""

from pathlib import Path


class ProjectNotFoundError(RuntimeError):
    """Raised when no Forge project root can be found."""


def is_forge_project(path: Path) -> bool:
    """Return true when `path` looks like a Forge project root."""

    return (
        (path / ".forge" / "config.yaml").is_file()
        and (path / ".forge" / "state.json").is_file()
    )


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest Forge project root at or above `start`."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if is_forge_project(candidate):
            return candidate
    raise ProjectNotFoundError("No Forge project found. Run `forge init` first.")
