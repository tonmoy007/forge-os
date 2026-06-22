"""Tests for channel message normalization (FR-CH-001, FR-SEC-005)."""

from __future__ import annotations

from forge_os.channels.normalize import normalize_message
from forge_os.schemas.channel import ChannelMessage, TrustLevel


def test_normalize_produces_user_prompt_submit():
    event = normalize_message(ChannelMessage(channel_id="console", sender="alice", text="hi"))
    assert event.event_type == "UserPromptSubmit"
    assert event.actor.type == "channel"
    assert event.actor.id == "alice"


def test_normalize_carries_untrusted_envelope():
    event = normalize_message(ChannelMessage(channel_id="console", sender="bob", text="x"))
    assert event.payload["trust_level"] == "untrusted"
    assert event.payload["source"] == "channel"
    assert event.payload["text"] == "x"
    assert event.payload["channel_id"] == "console"


def test_default_trust_level_is_untrusted():
    message = ChannelMessage(channel_id="c", sender="s", text="t")
    assert message.trust_level is TrustLevel.UNTRUSTED
