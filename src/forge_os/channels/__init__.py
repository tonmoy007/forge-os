"""Phase 11 channel subsystem (FR-CH-001..003).

Local-first channel interaction: a portable channel adapter interface, a console
adapter, and message normalization into Forge lifecycle events. Domain-only —
never imports ``cli/`` or ``use_cases/``.
"""

from forge_os.channels.base import BaseChannelAdapter, ChannelAdapter
from forge_os.channels.console import ConsoleChannelAdapter
from forge_os.channels.errors import ChannelError
from forge_os.channels.normalize import normalize_message

__all__ = [
    "BaseChannelAdapter",
    "ChannelAdapter",
    "ChannelError",
    "ConsoleChannelAdapter",
    "normalize_message",
]
