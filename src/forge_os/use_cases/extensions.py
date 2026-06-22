"""Phase 11 extension/plugin use cases (FR-EXT-001..004).

The sole bridge between the ``plug`` CLI and the extension domain. Catches
domain exceptions and returns plain dicts (never raw Typer/Rich types). Builds
a fail-closed SecurityEnforcer (default profile denies all capabilities) the
same way ``SecurityUseCases`` does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.extensions.errors import ExtensionError
from forge_os.extensions.installer import install_extension, remove_extension
from forge_os.extensions.store import ExtensionStore
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.security import SecurityProfile


class ExtensionUseCases:
    """Aggregate extension list/install/remove operations for one project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.store = ExtensionStore(self.project_root)
        self.audit_log = SecurityAuditLog(self.project_root)
        # Default profile denies all capabilities (fail-closed). Loading the
        # project's configured profile is a follow-up, mirroring SecurityUseCases.
        self.profile = SecurityProfile(profile_id="default")
        self.enforcer = SecurityEnforcer(self.project_root, self.profile, self.audit_log)

    def list_extensions(self) -> list[dict[str, Any]]:
        """Return installed extensions as JSON-safe dicts."""
        return [ext.model_dump(mode="json") for ext in self.store.list_installed()]

    def install(self, source_path: str, *, allow_unsigned: bool = False) -> dict[str, Any]:
        """Install a local extension from *source_path*.

        Returns ``{"success": True, "extension": {...}}`` or
        ``{"success": False, "error": "..."}``.
        """
        try:
            installed = install_extension(
                Path(source_path),
                self.store,
                self.enforcer,
                allow_unsigned=allow_unsigned,
                audit_log=self.audit_log,
            )
        except ExtensionError as exc:
            return {"success": False, "error": str(exc)}
        return {"success": True, "extension": installed.model_dump(mode="json")}

    def remove(self, name: str) -> dict[str, Any]:
        """Remove an installed extension by name."""
        if not remove_extension(name, self.store):
            return {"success": False, "error": f"extension '{name}' is not installed"}
        return {"success": True, "name": name}
