"""Phase 11 channel subsystem (FR-CH-001..003).

Local-first channel interaction: a portable channel adapter interface, a console
adapter, and message normalization into Forge lifecycle events. Domain-only —
never imports ``cli/`` or ``use_cases/``.
"""

from forge_os.channels.base import BaseChannelAdapter, ChannelAdapter
from forge_os.channels.console import ConsoleChannelAdapter
from forge_os.channels.errors import (
    ChannelAlreadyBoundError,
    ChannelDuplicateError,
    ChannelError,
    ChannelPermissionError,
    ChannelRateLimitError,
    UnboundSenderError,
)
from forge_os.channels.identity import ChannelIdentityStore
from forge_os.channels.intake import FeedbackQueue
from forge_os.channels.normalize import normalize_message
from forge_os.channels.policy import authorize_channel_action

__all__ = [
    "BaseChannelAdapter",
    "ChannelAdapter",
    "ChannelAlreadyBoundError",
    "ChannelDuplicateError",
    "ChannelError",
    "ChannelIdentityStore",
    "ChannelPermissionError",
    "ChannelRateLimitError",
    "ConsoleChannelAdapter",
    "FeedbackQueue",
    "UnboundSenderError",
    "authorize_channel_action",
    "normalize_message",
]
