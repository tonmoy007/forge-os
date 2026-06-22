"""Channel subsystem exceptions (typed, fail-loud)."""

from __future__ import annotations


class ChannelError(RuntimeError):
    """Base error for the channel subsystem."""


class ChannelPermissionError(ChannelError):
    """Raised when a channel action is denied by the security profile (FR-CH-004)."""


class UnboundSenderError(ChannelError):
    """Raised when an unbound sender attempts a non-read action (FR-CH-005)."""


class ChannelRateLimitError(ChannelError):
    """Raised when a sender exceeds the feedback rate limit (P11.07)."""


class ChannelDuplicateError(ChannelError):
    """Raised when duplicate feedback is submitted (P11.07 dedup)."""


class ChannelAlreadyBoundError(ChannelError):
    """Raised when re-pairing a sender that is already bound (FR-CH-005).

    A confirmed binding must be explicitly unbound before re-pairing, so a
    re-pair cannot silently destroy it.
    """
