"""Local installed-extension index (atomic, ``forge_dir``-injected).

Persists to ``<project_root>/.forge/extensions/installed.json``. The project
root is injected by the caller (L001/L005) so tests use ``tmp_path``; this
module never reads ``Path.home()`` and never writes canonical pipeline state.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from forge_os.schemas.extension import InstalledExtension

INDEX_RELPATH = Path(".forge") / "extensions" / "installed.json"


class ExtensionStore:
    """The set of locally installed extensions for one project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.index_path = self.project_root / INDEX_RELPATH

    def list_installed(self) -> list[InstalledExtension]:
        """Return all installed extensions (empty if none)."""
        if not self.index_path.exists():
            return []
        raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [InstalledExtension.model_validate(item) for item in raw]

    def get(self, name: str) -> InstalledExtension | None:
        """Return the installed extension named *name*, or ``None``."""
        return next(
            (ext for ext in self.list_installed() if ext.manifest.name == name),
            None,
        )

    def record(self, extension: InstalledExtension) -> None:
        """Insert or replace *extension* by name."""
        kept = [
            ext
            for ext in self.list_installed()
            if ext.manifest.name != extension.manifest.name
        ]
        kept.append(extension)
        self._write(kept)

    def remove(self, name: str) -> bool:
        """Remove the extension named *name*; return ``True`` if one was removed."""
        installed = self.list_installed()
        remaining = [ext for ext in installed if ext.manifest.name != name]
        if len(remaining) == len(installed):
            return False
        self._write(remaining)
        return True

    def _write(self, extensions: list[InstalledExtension]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [ext.model_dump(mode="json") for ext in extensions],
            indent=2,
            sort_keys=False,
        )
        # Atomic write (tempfile + replace), mirroring StateManager discipline.
        handle, tmp = tempfile.mkstemp(dir=str(self.index_path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(payload)
            os.replace(tmp, self.index_path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
