"""Channel adapter interface (FR-CH-001).

Mirrors the KernelAdapter Protocol + Base pattern (``adapters/base.py``): a small
portable interface for translating chat messages to and from Forge. Console/dummy
only this phase — real network channels arrive later as plugins.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from forge_os.channels.normalize import normalize_message
from forge_os.events.model import LifecycleEvent
from forge_os.schemas.channel import ChannelMessage, TrustLevel


@runtime_checkable
class ChannelAdapter(Protocol):
    """Portable interface translating channel messages to/from Forge events."""

    channel_id: str

    def on_message(self, text: str, sender: str) -> LifecycleEvent:
        """Translate an inbound chat message into a normalized Forge event."""
        ...

    def send_message(self, text: str) -> None:
        """Emit an outbound message on this channel."""
        ...


class BaseChannelAdapter:
    """Convenience base: normalizes inbound messages; subclasses implement send."""

    channel_id = "base"

    def on_message(self, text: str, sender: str) -> LifecycleEvent:
        message = ChannelMessage(
            channel_id=self.channel_id,
            sender=sender,
            text=text,
            trust_level=TrustLevel.UNTRUSTED,
        )
        return normalize_message(message)

    def send_message(self, text: str) -> None:
        raise NotImplementedError
