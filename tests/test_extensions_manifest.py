"""Tests for extension manifest loading/validation (FR-EXT-001)."""

from __future__ import annotations

import pytest
import yaml

from forge_os.extensions.errors import ManifestError
from forge_os.extensions.manifest import load_manifest
from forge_os.schemas.extension import ExtensionPoint

VALID = {
    "name": "my-ext",
    "version": "1.0.0",
    "extension_point": "gate_criteria",
    "entry_point": "my_ext:Gate",
    "permissions": [],
}


def _write(dir_path, data) -> None:
    (dir_path / "extension.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_load_manifest_from_directory(tmp_path):
    _write(tmp_path, VALID)
    manifest = load_manifest(tmp_path)
    assert manifest.name == "my-ext"
    assert manifest.extension_point is ExtensionPoint.GATE_CRITERIA


def test_load_manifest_from_file(tmp_path):
    _write(tmp_path, VALID)
    manifest = load_manifest(tmp_path / "extension.yaml")
    assert manifest.version == "1.0.0"


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_invalid_yaml_raises(tmp_path):
    (tmp_path / "extension.yaml").write_text("name: [unterminated", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_non_mapping_manifest_raises(tmp_path):
    (tmp_path / "extension.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_missing_required_field_raises(tmp_path):
    bad = dict(VALID)
    del bad["version"]
    _write(tmp_path, bad)
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_empty_name_raises(tmp_path):
    bad = dict(VALID)
    bad["name"] = "   "
    _write(tmp_path, bad)
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_unknown_extension_point_raises(tmp_path):
    bad = dict(VALID)
    bad["extension_point"] = "nonsense"
    _write(tmp_path, bad)
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)
