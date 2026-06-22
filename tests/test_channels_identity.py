"""Tests for channel identity binding (FR-CH-005)."""

from __future__ import annotations

import pytest

from forge_os.channels.errors import ChannelAlreadyBoundError
from forge_os.channels.identity import ChannelIdentityStore


def test_unknown_sender_is_unbound(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    assert store.get("console", "alice") is None
    assert store.is_bound("console", "alice") is False


def test_pairing_then_confirm_binds(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    code = store.begin_pairing("console", "alice")
    assert store.is_bound("console", "alice") is False
    assert store.confirm("console", "alice", code, "alice@forge") is True
    assert store.is_bound("console", "alice") is True
    identity = store.get("console", "alice")
    assert identity is not None
    assert identity.forge_identity == "alice@forge"
    assert identity.pairing_code is None


def test_confirm_wrong_code_fails(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    store.begin_pairing("console", "bob")
    assert store.confirm("console", "bob", "wrong", "bob@forge") is False
    assert store.is_bound("console", "bob") is False


def test_confirm_without_pairing_fails(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    assert store.confirm("console", "carol", "any", "carol@forge") is False


def test_identities_isolated_under_forge_dir(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    store.begin_pairing("console", "alice")
    assert (tmp_path / ".forge" / "channels" / "identities.json").exists()


def test_bindings_are_per_channel_and_sender(tmp_path):
    store = ChannelIdentityStore(tmp_path)
    code = store.begin_pairing("console", "alice")
    store.confirm("console", "alice", code, "alice@forge")
    assert store.is_bound("slack", "alice") is False


def test_begin_pairing_refuses_when_already_bound(tmp_path):
    # A re-pair must not silently destroy a confirmed binding (FR-CH-005).
    store = ChannelIdentityStore(tmp_path)
    code = store.begin_pairing("console", "alice")
    store.confirm("console", "alice", code, "alice@forge")
    with pytest.raises(ChannelAlreadyBoundError):
        store.begin_pairing("console", "alice")
    assert store.is_bound("console", "alice") is True


def test_confirm_is_one_time_and_rejects_code_reuse(tmp_path):
    # The pairing code is one-time: replay after a successful bind must fail
    # and must not rebind to a different identity.
    store = ChannelIdentityStore(tmp_path)
    code = store.begin_pairing("console", "alice")
    assert store.confirm("console", "alice", code, "alice@forge") is True
    assert store.confirm("console", "alice", code, "attacker@forge") is False
    identity = store.get("console", "alice")
    assert identity is not None
    assert identity.forge_identity == "alice@forge"
    assert identity.bound is True
