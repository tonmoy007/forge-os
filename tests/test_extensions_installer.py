"""Tests for install/remove orchestration: conflict, permission, signing gates."""

from __future__ import annotations

import pytest
import yaml

from forge_os.extensions.errors import (
    ExtensionConflictError,
    ExtensionPermissionError,
    ExtensionSignatureError,
)
from forge_os.extensions.installer import install_extension, remove_extension
from forge_os.extensions.store import ExtensionStore
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.security import CapabilityRule, SecurityPolicy, SecurityProfile


def _make_ext(dir_path, *, name="ext", signed=False, permissions=None):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "extension.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "version": "1.0.0",
                "extension_point": "gate_criteria",
                "entry_point": "pkg:Obj",
                "signed": signed,
                "permissions": permissions or [],
            }
        ),
        encoding="utf-8",
    )
    return dir_path


def _enforcer(project_root, *, allow=None, prompt=None) -> SecurityEnforcer:
    rules = [
        CapabilityRule(capability=name, policy=SecurityPolicy.ALLOW)
        for name in (allow or [])
    ]
    rules += [
        CapabilityRule(capability=name, policy=SecurityPolicy.PROMPT)
        for name in (prompt or [])
    ]
    profile = SecurityProfile(
        profile_id="test",
        default_policy=SecurityPolicy.DENY,
        capabilities=rules,
    )
    return SecurityEnforcer(project_root, profile, SecurityAuditLog(project_root))


def test_install_unsigned_with_consent_records(tmp_path):
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    installed = install_extension(
        src, store, _enforcer(proj), allow_unsigned=True, audit_log=SecurityAuditLog(proj)
    )
    assert installed.manifest.name == "ext"
    assert installed.signature_verified is False
    assert store.get("ext") is not None


def test_install_unsigned_without_consent_raises(tmp_path):
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    with pytest.raises(ExtensionSignatureError):
        install_extension(src, store, _enforcer(proj))
    assert store.list_installed() == []


def test_self_declared_signed_is_not_trusted(tmp_path):
    # No real signature verification exists this phase (FR-EXT-004 deferred), so a
    # manifest claiming signed:true cannot bypass consent and is never recorded as verified.
    src = _make_ext(tmp_path / "src", signed=True)
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    with pytest.raises(ExtensionSignatureError):
        install_extension(src, store, _enforcer(proj))
    assert store.list_installed() == []
    installed = install_extension(
        src, store, _enforcer(proj), allow_unsigned=True, audit_log=SecurityAuditLog(proj)
    )
    assert installed.signature_verified is False


def test_duplicate_install_raises_conflict(tmp_path):
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    install_extension(
        src, store, _enforcer(proj), allow_unsigned=True, audit_log=SecurityAuditLog(proj)
    )
    with pytest.raises(ExtensionConflictError):
        install_extension(src, store, _enforcer(proj), allow_unsigned=True)
    # The conflict gate runs first and leaves state untouched (exactly one entry).
    assert len(store.list_installed()) == 1


def test_denied_permission_rejected_fail_closed(tmp_path):
    src = _make_ext(tmp_path / "src", permissions=["network"])
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    with pytest.raises(ExtensionPermissionError):
        install_extension(src, store, _enforcer(proj), allow_unsigned=True)
    assert store.list_installed() == []


def test_prompt_policy_rejected_fail_closed(tmp_path):
    # PROMPT maps to WARNED (no interactive prompt in this installer) and must NOT
    # be auto-approved — only an explicit ALLOW passes the gate.
    src = _make_ext(tmp_path / "src", permissions=["network"])
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    with pytest.raises(ExtensionPermissionError):
        install_extension(
            src, store, _enforcer(proj, prompt=["network"]), allow_unsigned=True
        )
    assert store.list_installed() == []


def test_allowed_permission_installs(tmp_path):
    src = _make_ext(tmp_path / "src", permissions=["network"])
    proj = tmp_path / "proj"
    installed = install_extension(
        src,
        ExtensionStore(proj),
        _enforcer(proj, allow=["network"]),
        allow_unsigned=True,
        audit_log=SecurityAuditLog(proj),
    )
    assert installed.manifest.permissions == ["network"]


def test_unsigned_install_writes_audit_entry(tmp_path):
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    audit = SecurityAuditLog(proj)
    install_extension(
        src, ExtensionStore(proj), _enforcer(proj), allow_unsigned=True, audit_log=audit
    )
    actions = [entry["action"] for entry in audit.read_all()]
    assert "ExtensionUnsignedInstalled" in actions


def test_remove_extension_helper(tmp_path):
    src = _make_ext(tmp_path / "src")
    proj = tmp_path / "proj"
    store = ExtensionStore(proj)
    install_extension(
        src, store, _enforcer(proj), allow_unsigned=True, audit_log=SecurityAuditLog(proj)
    )
    assert remove_extension("ext", store) is True
    assert remove_extension("ext", store) is False
