from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SecurityPolicy(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"

class SecurityDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    WARNED = "warned"
    FAILED = "failed"

class CapabilityRule(BaseModel):
    """Rule for a specific tool or system capability."""
    capability: str
    policy: SecurityPolicy
    scope: dict[str, Any] | None = None
    requires_approval: bool = False
    timeout_seconds: int | None = None

class SecurityProfile(BaseModel):
    """Defines allowed capabilities and approval requirements."""
    schema_version: str = "0.1.0"
    profile_id: str
    default_policy: SecurityPolicy = SecurityPolicy.DENY
    capabilities: Sequence[CapabilityRule] = Field(default_factory=list)
    audit_enabled: bool = True

class SecurityAuditEntry(BaseModel):
    """A single entry in the security audit log."""
    schema_version: str = "0.1.0"
    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    actor: dict[str, Any]
    action: str
    target: Any | None = None
    capability: str | None = None
    decision: SecurityDecision
    approval: dict[str, Any] | None = None
    reason: str | None = None
    redactions: Sequence[str] = Field(default_factory=list)
