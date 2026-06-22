"""Phase 11 channel message schemas (additive — FR-CH-001, FR-SEC-005).

New schema file. Imports only stdlib + pydantic (schemas are pure data). No
existing schema/contract is modified.
"""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class TrustLevel(StrEnum):
    """Trust label for channel-sourced input (FR-SEC-005 — labeling, not enforcement)."""

    UNTRUSTED = "untrusted"
    TRUSTED = "trusted"


class ChannelMessage(BaseModel):
    """A normalized inbound message from a channel adapter."""

    channel_id: str
    sender: str
    text: str
    trust_level: TrustLevel = TrustLevel.UNTRUSTED


class ChannelIdentity(BaseModel):
    """Binding between a channel sender and a Forge identity (FR-CH-005).

    ``bound`` gates non-read actions; ``pairing_code`` holds the one-time code a
    HITL operator confirms to complete the binding.
    """

    channel_id: str
    sender: str
    forge_identity: str | None = None
    bound: bool = False
    pairing_code: str | None = None


class FeedbackItem(BaseModel):
    """A piece of channel feedback queued for Stage 10 triage (FR-CH-002, P11.05)."""

    feedback_id: str = Field(default_factory=lambda: f"fb-{uuid4()}")
    channel_id: str
    sender: str
    text: str
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"
