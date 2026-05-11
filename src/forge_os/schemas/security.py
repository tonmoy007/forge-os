from datetime import datetime
from enum import Enum
from typing import Optional, Sequence, Any
from pydantic import BaseModel, Field

class SecurityPolicy(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PROMPT = "prompt"

class SecurityDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    WARNED = "warned"
    FAILED = "failed"

class CapabilityRule(BaseModel):
    """Rule for a specific tool or system capability."""
    capability: str
    policy: SecurityPolicy
    scope: Optional[dict[str, Any]] = None
    requires_approval: bool = False
    timeout_seconds: Optional[int] = None

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
    target: Optional[Any] = None
    capability: Optional[str] = None
    decision: SecurityDecision
    approval: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    redactions: Sequence[str] = Field(default_factory=list)
