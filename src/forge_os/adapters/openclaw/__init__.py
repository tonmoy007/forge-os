"""OpenClaw kernel adapter package (Phase 11, Slice 3 — FR-OCA-001..006).

Optional execution surface built on the Phase 08 ACP foundation. OpenClaw is never
a required dependency; see ``plan/OPENCLAW_ADAPTER_ARCHITECTURE.md``.
"""

from forge_os.adapters.openclaw.adapter import (
    FORGE_PROTECTED_FILES,
    OPENCLAW_TOOL_MAP,
    OpenClawAdapter,
    OpenClawError,
    adapter_id,
    bridge_webhook,
    build_openclaw_session_config,
    canonical_relpath,
    is_protected_path,
    map_tool_policy,
    sync_insights_back,
    wire_to_abstract,
)
from forge_os.adapters.openclaw.channel import OpenClawChannelAdapter

__all__ = [
    "FORGE_PROTECTED_FILES",
    "OPENCLAW_TOOL_MAP",
    "OpenClawAdapter",
    "OpenClawChannelAdapter",
    "OpenClawError",
    "adapter_id",
    "bridge_webhook",
    "build_openclaw_session_config",
    "canonical_relpath",
    "is_protected_path",
    "map_tool_policy",
    "sync_insights_back",
    "wire_to_abstract",
]
