"""Atomic, validated writes for `.forge/config.yaml`.

`config/loader.py` is the single source of truth for *reading* config; this is its
write counterpart. Every write dumps a validated :class:`ForgeConfig` so the on-disk
YAML always matches the schema, and stages the bytes through a temp file in the same
directory followed by :func:`os.replace`, so a crash mid-write can never leave a
truncated `config.yaml` behind.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import yaml

from forge_os.config.loader import ConfigError
from forge_os.schemas.config import ForgeConfig


def save_config(path: Path, config: ForgeConfig) -> None:
    """Persist a validated ``config`` to ``path`` atomically.

    Keys are written in declaration order (``sort_keys=False``) for readable diffs.
    The model is serialized with ``mode="json"`` so enums/paths round-trip the same
    way the loader expects to read them back. Any filesystem failure (read-only dir,
    full disk, bad path) is wrapped in :class:`ConfigError`, mirroring the loader's
    read path, so callers get a typed domain error instead of a raw ``OSError``.
    """

    path = Path(path)
    payload = yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Same-directory temp file keeps os.replace an atomic rename (no cross-device move).
        handle_fd, tmp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_path, path)
        finally:
            # After a successful replace the temp file is gone; clean up only on
            # failure, and never let cleanup mask the real write error.
            with contextlib.suppress(OSError):
                if tmp_path.exists():
                    tmp_path.unlink()
    except OSError as exc:
        raise ConfigError(f"Could not write config file: {path}: {exc}") from exc
