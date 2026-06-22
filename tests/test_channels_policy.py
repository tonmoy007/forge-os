"""Tests for channel action authorization (FR-CH-004 default-deny, FR-CH-005)."""

from __future__ import annotations

import pytest

from forge_os.channels.errors import ChannelPermissionError, UnboundSenderError
from forge_os.channels.policy import authorize_channel_action
from forge_os.project.security_audit import SecurityAuditLog
from forge_os.project.security_enforcer import SecurityEnforcer
from forge_os.schemas.channel import ChannelIdentity
from forge_os.schemas.security import CapabilityRule, SecurityPolicy, SecurityProfile


def _enforcer(tmp_path, *, allow=None) -> SecurityEnforcer:
    rules = [
        CapabilityRule(capability=name, policy=SecurityPolicy.ALLOW)
        for name in (allow or [])
    ]
    profile = SecurityProfile(
        profile_id="test", default_policy=SecurityPolicy.DENY, capabilities=rules
    )
    return SecurityEnforcer(tmp_path, profile, SecurityAuditLog(tmp_path))


def _bound(sender="alice") -> ChannelIdentity:
    return ChannelIdentity(
        channel_id="console", sender=sender, bound=True, forge_identity=f"{sender}@forge"
    )


def test_status_allowed_for_unbound(tmp_path):
    authorize_channel_action("status", None, _enforcer(tmp_path))


def test_feedback_allowed_for_unbound(tmp_path):
    authorize_channel_action("feedback", None, _enforcer(tmp_path))


def test_os_action_unbound_raises(tmp_path):
    with pytest.raises(UnboundSenderError):
        authorize_channel_action("spawn", None, _enforcer(tmp_path))


def test_os_action_bound_default_deny_raises(tmp_path):
    with pytest.raises(ChannelPermissionError):
        authorize_channel_action("spawn", _bound(), _enforcer(tmp_path))


def test_os_action_bound_allowed_passes(tmp_path):
    authorize_channel_action("spawn", _bound(), _enforcer(tmp_path, allow=["spawn"]))


def test_unconfirmed_identity_treated_as_unbound(tmp_path):
    unbound = ChannelIdentity(channel_id="console", sender="bob", bound=False)
    with pytest.raises(UnboundSenderError):
        authorize_channel_action("spawn", unbound, _enforcer(tmp_path))
