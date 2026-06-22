"""Console/dummy channel adapter — no network (FR-CH-001, P11.02)."""

from __future__ import annotations

from collections.abc import Callable

from forge_os.channels.base import BaseChannelAdapter


class ConsoleChannelAdapter(BaseChannelAdapter):
    """A local channel that emits outbound messages through a sink (default print)."""

    channel_id = "console"

    def __init__(self, sink: Callable[[str], None] | None = None) -> None:
        self._sink: Callable[[str], None] = sink or print

    def send_message(self, text: str) -> None:
        self._sink(text)
