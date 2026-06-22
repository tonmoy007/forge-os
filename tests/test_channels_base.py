"""Tests for the channel adapter interface + console adapter (FR-CH-001)."""

from __future__ import annotations

import pytest

from forge_os.channels.base import BaseChannelAdapter, ChannelAdapter
from forge_os.channels.console import ConsoleChannelAdapter


def test_console_adapter_satisfies_protocol():
    assert isinstance(ConsoleChannelAdapter(), ChannelAdapter)


def test_console_send_message_uses_sink():
    sent: list[str] = []
    adapter = ConsoleChannelAdapter(sink=sent.append)
    adapter.send_message("release notes")
    assert sent == ["release notes"]


def test_on_message_returns_normalized_event():
    event = ConsoleChannelAdapter().on_message("hi", "alice")
    assert event.event_type == "UserPromptSubmit"
    assert event.payload["channel_id"] == "console"
    assert event.payload["trust_level"] == "untrusted"


def test_base_send_message_not_implemented():
    with pytest.raises(NotImplementedError):
        BaseChannelAdapter().send_message("x")
