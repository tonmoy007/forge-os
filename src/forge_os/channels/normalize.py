"""Normalize inbound channel messages into Forge lifecycle events (FR-CH-001)."""

from __future__ import annotations

from forge_os.events.model import LifecycleEvent, new_event
from forge_os.schemas.channel import ChannelMessage


def normalize_message(message: ChannelMessage) -> LifecycleEvent:
    """Translate a channel message into a ``UserPromptSubmit`` lifecycle event.

    The untrusted-input envelope (FR-SEC-005) travels in the payload as
    ``trust_level`` and ``source`` so downstream validators can see provenance.
    """
    return new_event(
        "UserPromptSubmit",
        actor_type="channel",
        actor_id=message.sender,
        payload={
            "channel_id": message.channel_id,
            "text": message.text,
            "trust_level": message.trust_level.value,
            "source": "channel",
        },
    )
