"""Extension subsystem exceptions (typed, fail-loud)."""

from __future__ import annotations


class ExtensionError(RuntimeError):
    """Base error for the extension subsystem."""


class ManifestError(ExtensionError):
    """Raised when an extension manifest is missing or invalid."""


class ExtensionConflictError(ExtensionError):
    """Raised when an extension conflicts with an already-installed one."""


class ExtensionPermissionError(ExtensionError):
    """Raised when an extension's declared permissions are denied (fail-closed)."""


class ExtensionSignatureError(ExtensionError):
    """Raised when an unsigned extension install is not explicitly allowed."""
