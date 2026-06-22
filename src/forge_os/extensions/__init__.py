"""Phase 11 extension/plugin subsystem (FR-EXT-001..004).

Local-first extension management: declarative manifests, an atomic local
install index, fail-closed permission validation, and conflict detection.
Domain-only — never imports ``cli/`` or ``use_cases/``.
"""

from forge_os.extensions.errors import (
    ExtensionConflictError,
    ExtensionError,
    ExtensionPermissionError,
    ExtensionSignatureError,
    ManifestError,
)
from forge_os.extensions.installer import (
    detect_conflicts,
    install_extension,
    remove_extension,
    validate_permissions,
)
from forge_os.extensions.manifest import load_manifest
from forge_os.extensions.store import ExtensionStore

__all__ = [
    "ExtensionConflictError",
    "ExtensionError",
    "ExtensionPermissionError",
    "ExtensionSignatureError",
    "ExtensionStore",
    "ManifestError",
    "detect_conflicts",
    "install_extension",
    "load_manifest",
    "remove_extension",
    "validate_permissions",
]
