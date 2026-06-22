"""Phase 11 extension/plugin manifest schemas (additive — FR-EXT-001..004).

New schema file. Imports only stdlib + pydantic (layer rule: schemas are pure data).
No existing schema/contract is modified.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ExtensionPoint(StrEnum):
    """The four published extension points (FR-EXT-001)."""

    KERNEL_ADAPTER = "kernel_adapter"
    STAGE_AGENT = "stage_agent"
    GATE_CRITERIA = "gate_criteria"
    PROFILE_PACK = "profile_pack"


class ExtensionManifest(BaseModel):
    """Declarative manifest an extension ships in its ``extension.yaml``.

    ``permissions`` are capability names validated against the project's
    SecurityProfile at install time (FR-EXT-003). ``signed`` is reserved for
    FR-EXT-004 remote-registry signing (deferred this phase; local installs are
    unsigned and require explicit ``--allow-unsigned``).
    """

    schema_version: str = "0.1.0"
    name: str
    version: str
    extension_point: ExtensionPoint
    entry_point: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    signed: bool = False
    forge_min_version: str | None = None

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("extension name must be non-empty")
        return value

    @field_validator("version")
    @classmethod
    def _version_nonempty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("extension version must be non-empty")
        return value


class InstalledExtension(BaseModel):
    """A manifest plus install bookkeeping, persisted in the local index."""

    schema_version: str = "0.1.0"
    manifest: ExtensionManifest
    source_path: str
    installed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    signature_verified: bool = False
