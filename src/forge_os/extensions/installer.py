"""Install/remove orchestration with conflict + permission gating.

Implements FR-EXT-002 (install/remove), FR-EXT-003 (fail-closed permission
validation via the project SecurityEnforcer), and the FR-EXT-004 local-install
path (unsigned installs require explicit consent and are audited).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from forge_os.extensions.errors import (
    ExtensionConflictError,
    ExtensionPermissionError,
    ExtensionSignatureError,
)
from forge_os.extensions.manifest import load_manifest
from forge_os.schemas.extension import ExtensionManifest, InstalledExtension
from forge_os.schemas.security import SecurityAuditEntry, SecurityDecision

if TYPE_CHECKING:
    from forge_os.extensions.store import ExtensionStore
    from forge_os.project.security_enforcer import SecurityEnforcer

EXTENSION_ACTOR = {"type": "extension", "id": "forge-plug"}


def detect_conflicts(
    manifest: ExtensionManifest,
    installed: list[InstalledExtension],
) -> list[str]:
    """Return human-readable conflict reasons (FR-EXT-002 conflict detection).

    A name collision with an already-installed extension is a conflict.
    """
    conflicts: list[str] = []
    for existing in installed:
        if existing.manifest.name == manifest.name:
            conflicts.append(
                f"extension '{manifest.name}' already installed "
                f"(version {existing.manifest.version})"
            )
    return conflicts


def validate_permissions(
    manifest: ExtensionManifest,
    enforcer: SecurityEnforcer,
) -> None:
    """Fail-closed permission check (FR-EXT-003).

    Each declared permission is validated against the project SecurityProfile;
    any capability that is not explicitly ``ALLOWED`` rejects the install.
    Extensions declaring no permissions pass with no checks.
    """
    for permission in manifest.permissions:
        decision = enforcer.validate_action(
            EXTENSION_ACTOR,
            "install_extension",
            target=manifest.name,
            capability=permission,
        )
        # Fail-closed: only an explicit ALLOW passes. DENY rejects, and so does
        # PROMPT (which the enforcer maps to WARNED with no interactive prompt in
        # this non-interactive installer) — the gate never auto-approves an
        # unconfirmed capability.
        if decision != SecurityDecision.ALLOWED:
            raise ExtensionPermissionError(
                f"extension '{manifest.name}' requires capability '{permission}' "
                f"not allowed by the security profile (decision={decision})"
            )


def verify_signature(source: Path, manifest: ExtensionManifest) -> bool:
    """Whether a *trusted, verified* signature is present.

    Cryptographic verification (Sigstore / remote registry, FR-EXT-004) is
    deferred. Until it lands, no local extension can be verified, so this always
    returns ``False`` — a manifest's self-declared ``signed`` flag is untrusted
    input and never grants a consent bypass.
    """
    return False


def install_extension(
    source: Path,
    store: ExtensionStore,
    enforcer: SecurityEnforcer,
    *,
    allow_unsigned: bool = False,
    audit_log=None,
) -> InstalledExtension:
    """Install a local extension, gating on conflicts, permissions, and signing.

    Order is deliberate and fail-loud: conflict → permission (fail-closed) →
    signing. Nothing is recorded until every gate passes.
    """
    source = Path(source)
    manifest = load_manifest(source)

    conflicts = detect_conflicts(manifest, store.list_installed())
    if conflicts:
        raise ExtensionConflictError("; ".join(conflicts))

    validate_permissions(manifest, enforcer)

    verified = verify_signature(source, manifest)
    if not verified and not allow_unsigned:
        raise ExtensionSignatureError(
            f"extension '{manifest.name}' is not verified; "
            f"pass allow_unsigned to install it"
        )

    installed = InstalledExtension(
        manifest=manifest,
        source_path=str(source.resolve()),
        signature_verified=verified,
    )
    store.record(installed)
    if not verified:
        # Audit only after the install is persisted, so the audit trail reflects
        # completed installs (FR-EXT-004).
        _audit_unsigned(manifest, audit_log)
    return installed


def remove_extension(name: str, store: ExtensionStore) -> bool:
    """Remove an installed extension by name; return ``True`` if removed."""
    return store.remove(name)


def _audit_unsigned(manifest: ExtensionManifest, audit_log) -> None:
    """Record an ``ExtensionUnsignedInstalled`` security-audit entry (FR-EXT-004).

    Unsigned local installs are a security-relevant decision, so they are
    written to the authoritative security audit log rather than the lifecycle
    event log. No-op when no audit log is supplied (pure-domain test paths).
    """
    if audit_log is None:
        return
    audit_log.log(
        SecurityAuditEntry(
            audit_id=f"EXT-UNSIGNED-{manifest.name}-{manifest.version}",
            actor=EXTENSION_ACTOR,
            action="ExtensionUnsignedInstalled",
            target=manifest.name,
            capability="extension_install",
            decision=SecurityDecision.WARNED,
            reason="Unsigned extension installed with allow_unsigned",
        )
    )
