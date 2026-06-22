"""Phase 11 channel message schemas (additive — FR-CH-001, FR-SEC-005).

New schema file. Imports only stdlib + pydantic (schemas are pure data). No
existing schema/contract is modified.
"""

from enum import StrEnum

from pydantic import BaseModel


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
