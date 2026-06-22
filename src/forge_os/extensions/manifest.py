"""Load and validate extension manifests (FR-EXT-001)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from forge_os.extensions.errors import ManifestError
from forge_os.schemas.extension import ExtensionManifest

MANIFEST_FILENAME = "extension.yaml"


def load_manifest(source: Path) -> ExtensionManifest:
    """Load an :class:`ExtensionManifest` from a source directory or manifest file.

    *source* may be a directory containing ``extension.yaml`` or the manifest
    file itself. Raises :class:`ManifestError` if missing or invalid.
    """

    source = Path(source)
    manifest_path = source / MANIFEST_FILENAME if source.is_dir() else source
    if not manifest_path.exists():
        raise ManifestError(f"No extension manifest found at {manifest_path}")

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {manifest_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestError(f"Manifest must be a mapping: {manifest_path}")

    try:
        return ExtensionManifest(**raw)
    except ValidationError as exc:
        raise ManifestError(f"Invalid extension manifest {manifest_path}: {exc}") from exc
