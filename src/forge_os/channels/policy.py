"""Channel action authorization (FR-CH-004 default-deny, FR-CH-005 identity-gated).

A channel sender may always perform SDLC read/feedback actions. Any other (OS-level)
action requires a *bound* identity AND an explicit ALLOW in the project security
profile — fail-closed by default. No channel->OS action exists yet this phase; this
gate is the enforcement point any future privileged channel action must pass through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forge_os.channels.errors import ChannelPermissionError, UnboundSenderError
from forge_os.schemas.security import SecurityDecision

if TYPE_CHECKING:
    from forge_os.project.security_enforcer import SecurityEnforcer
    from forge_os.schemas.channel import ChannelIdentity

# Actions an unbound sender may perform — SDLC read + feedback only, never the OS.
UNBOUND_ALLOWED = frozenset({"status", "feedback"})


def authorize_channel_action(
    action: str,
    identity: ChannelIdentity | None,
    enforcer: SecurityEnforcer,
) -> None:
    """Authorize a channel action; raise on denial (fail-closed).

    - SDLC read/feedback (``UNBOUND_ALLOWED``) is permitted regardless of binding.
    - Any other action requires a bound identity (FR-CH-005) AND an explicit
      ``ALLOWED`` decision from the security profile (FR-CH-004 default-deny).
    """
    if action in UNBOUND_ALLOWED:
        return

    bound = identity is not None and identity.bound
    if not bound:
        raise UnboundSenderError(
            f"sender must bind a Forge identity before action '{action}'"
        )

    decision = enforcer.validate_action(
        {"type": "channel", "id": identity.sender},
        f"channel_{action}",
        capability=action,
    )
    if decision != SecurityDecision.ALLOWED:
        raise ChannelPermissionError(
            f"channel action '{action}' not allowed by the security profile"
        )
