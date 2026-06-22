"""Tests for the local installed-extension index (forge_dir isolation)."""

from __future__ import annotations

from forge_os.extensions.store import ExtensionStore
from forge_os.schemas.extension import (
    ExtensionManifest,
    ExtensionPoint,
    InstalledExtension,
)


def _installed(name: str, version: str = "1.0.0") -> InstalledExtension:
    return InstalledExtension(
        manifest=ExtensionManifest(
            name=name,
            version=version,
            extension_point=ExtensionPoint.STAGE_AGENT,
            entry_point="pkg:Obj",
        ),
        source_path="/tmp/source",
    )


def test_empty_store_lists_nothing(tmp_path):
    assert ExtensionStore(tmp_path).list_installed() == []


def test_record_then_list_roundtrip(tmp_path):
    store = ExtensionStore(tmp_path)
    store.record(_installed("alpha"))
    assert [e.manifest.name for e in store.list_installed()] == ["alpha"]


def test_get_returns_named_extension(tmp_path):
    store = ExtensionStore(tmp_path)
    store.record(_installed("alpha"))
    found = store.get("alpha")
    assert found is not None and found.manifest.name == "alpha"
    assert store.get("missing") is None


def test_record_replaces_same_name(tmp_path):
    store = ExtensionStore(tmp_path)
    store.record(_installed("alpha", "1.0.0"))
    store.record(_installed("alpha", "2.0.0"))
    installed = store.list_installed()
    assert len(installed) == 1
    assert installed[0].manifest.version == "2.0.0"


def test_remove_existing_returns_true(tmp_path):
    store = ExtensionStore(tmp_path)
    store.record(_installed("alpha"))
    assert store.remove("alpha") is True
    assert store.list_installed() == []


def test_remove_missing_returns_false(tmp_path):
    assert ExtensionStore(tmp_path).remove("nope") is False


def test_index_isolated_under_forge_dir(tmp_path):
    store = ExtensionStore(tmp_path)
    store.record(_installed("alpha"))
    assert (tmp_path / ".forge" / "extensions" / "installed.json").exists()
