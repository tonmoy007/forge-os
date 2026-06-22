"""Tests for the ExtensionUseCases bridge layer (FR-EXT-001..004)."""

from __future__ import annotations

import yaml

from forge_os.project.security_audit import SecurityAuditLog
from forge_os.use_cases.extensions import ExtensionUseCases


def _make_ext(dir_path, *, name="ext", signed=False, permissions=None):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "extension.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "version": "1.0.0",
                "extension_point": "stage_agent",
                "entry_point": "pkg:Obj",
                "signed": signed,
                "permissions": permissions or [],
            }
        ),
        encoding="utf-8",
    )
    return dir_path


def test_list_empty(tmp_path):
    assert ExtensionUseCases(tmp_path / "proj").list_extensions() == []


def test_install_and_list(tmp_path):
    src = _make_ext(tmp_path / "src")
    use_cases = ExtensionUseCases(tmp_path / "proj")
    result = use_cases.install(str(src), allow_unsigned=True)
    assert result["success"] is True
    assert use_cases.list_extensions()[0]["manifest"]["name"] == "ext"


def test_install_unsigned_without_consent_fails(tmp_path):
    src = _make_ext(tmp_path / "src")
    result = ExtensionUseCases(tmp_path / "proj").install(str(src))
    assert result["success"] is False
    assert "unsigned" in result["error"]


def test_install_with_permission_denied_fail_closed(tmp_path):
    # Default profile denies all capabilities, so a declared permission is rejected.
    src = _make_ext(tmp_path / "src", signed=True, permissions=["network"])
    result = ExtensionUseCases(tmp_path / "proj").install(str(src))
    assert result["success"] is False


def test_unsigned_install_audits_through_use_case(tmp_path):
    # FR-EXT-004 end-to-end: the production install path must write the audit entry.
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    result = ExtensionUseCases(proj).install(str(src), allow_unsigned=True)
    assert result["success"] is True
    actions = [entry["action"] for entry in SecurityAuditLog(proj).read_all()]
    assert "ExtensionUnsignedInstalled" in actions


def test_remove_installed(tmp_path):
    src = _make_ext(tmp_path / "src")
    use_cases = ExtensionUseCases(tmp_path / "proj")
    use_cases.install(str(src), allow_unsigned=True)
    assert use_cases.remove("ext")["success"] is True


def test_remove_missing(tmp_path):
    result = ExtensionUseCases(tmp_path / "proj").remove("nope")
    assert result["success"] is False
