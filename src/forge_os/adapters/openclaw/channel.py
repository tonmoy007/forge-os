"""OpenClaw channel reuse (FR-OCA-004).

Exposes OpenClaw's channel surface to Forge's Channel Adapter Layer through the
*same* ``ChannelAdapter`` Protocol the console adapter uses (``channels/base.py``).
Feedback and status queries flow through Forge's existing channel pipeline — no
extra bot registration, no parallel channel stack.

v0.1: outbound messages are buffered/logged. Wiring them to the OpenClaw Gateway's
channel API lands with the transport (P11.08); inbound normalization is fully real.
"""

from __future__ import annotations

import logging

from forge_os.channels.base import BaseChannelAdapter

log = logging.getLogger("forge.adapters.openclaw.channel")


class OpenClawChannelAdapter(BaseChannelAdapter):
    """Bridge OpenClaw channels onto Forge's ChannelAdapter Protocol (FR-OCA-004).

    Inbound messages are normalized by the inherited ``on_message`` (untrusted by
    default, like every channel). Outbound messages are buffered in ``sent`` until
    the Gateway channel transport is wired.
    """

    channel_id = "openclaw"

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_message(self, text: str) -> None:
        # Placeholder transport: buffer + log. Replaced by a Gateway channel POST
        # once the OpenClaw channel API contract is published (P11.08).
        self.sent.append(text)
        log.debug("openclaw channel send (buffered): %s", text)
