"""Phase 10 domain-level read-only skill record access (P10.15).

Skill lifecycle (propose/approve/install) stays in `use_cases/skills.py`;
this reader exists so domain code never imports upward into use_cases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("forge.context.skills_reader")


class SkillReader:
    """Read `~/.forge/skills/*.yaml` records without mutating them."""

    def __init__(self, forge_dir: Path | None = None) -> None:
        base = forge_dir if forge_dir is not None else Path.home() / ".forge"
        self.skills_dir = base / "skills"

    def list_records(self) -> list[dict[str, Any]]:
        """Parse every skill YAML record, skipping malformed files with a warning."""
        # is_dir (not exists): a stray FILE named `skills` would make iterdir
        # raise NotADirectoryError; treat it like an absent skills store.
        if not self.skills_dir.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(self.skills_dir.iterdir()):
            if path.suffix != ".yaml":
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                log.warning("Skipping malformed skill record %s: %s", path, exc)
                continue
            if not isinstance(data, dict):
                log.warning("Skipping malformed skill record %s: not a YAML mapping", path)
                continue
            data.setdefault("name", path.stem)
            records.append(data)
        return records

    def get(self, name: str) -> dict[str, Any] | None:
        """Return the full record for *name*, or None when unknown."""
        for record in self.list_records():
            if record.get("name") == name:
                return record
        return None
