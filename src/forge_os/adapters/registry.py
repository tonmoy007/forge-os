"""Phase 05+ adapter registry and config selection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from forge_os.adapters.base import BaseKernelAdapter, KernelAdapter
from forge_os.adapters.dummy import DummyAdapter
from forge_os.schemas.config import ForgeConfig

if TYPE_CHECKING:
    from forge_os.events.store import EventStore

AdapterFactory = Callable[[Path, dict[str, object]], KernelAdapter]

ADAPTER_PRIORITY: tuple[str, ...] = (
    "dummy",
    "claude_code",
    "claude_raw",
    "claude_sdk",
    "codex",
    "openclaw",
    "opencode",
    "local_llm",
    "human",
)

ADAPTER_CLASS_NAMES: dict[str, str] = {
    "dummy": "DummyAdapter",
    "claude_code": "ClaudeCodeAdapter",
    "claude_raw": "ClaudeRawAdapter",
    "claude_sdk": "ClaudeSDKAdapter",
    "codex": "CodexAdapter",
    "openclaw": "OpenClawAdapter",
    "opencode": "OpenCodeAdapter",
    "local_llm": "LocalLLMAdapter",
    "human": "HumanAdapter",
}


class AdapterRegistryError(RuntimeError):
    """Raised when adapter selection or construction fails."""


class PlaceholderAdapter(BaseKernelAdapter):
    """Configured placeholder for adapters whose optional dep is missing."""

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id

    def spawn_agent(self, persona, context, tools):  # type: ignore[no-untyped-def]
        class_name = ADAPTER_CLASS_NAMES.get(self.adapter_id, self.adapter_id)
        raise AdapterRegistryError(
            f"{class_name} is configured but not available. "
            "Check that the optional dependency is installed."
        )


class AdapterRegistry:
    """Construct adapters by id without provider-specific imports in core."""

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, adapter_id: str, factory: AdapterFactory) -> None:
        if not adapter_id.strip():
            raise AdapterRegistryError("Adapter id is required.")
        self._factories[adapter_id] = factory

    def create(
        self,
        adapter_id: str,
        project_root: Path,
        config: dict[str, object],
    ) -> KernelAdapter:
        factory = self._factories.get(adapter_id)
        if factory is None:
            if adapter_id in ADAPTER_PRIORITY:
                return PlaceholderAdapter(adapter_id)
            raise AdapterRegistryError(f"Unknown adapter `{adapter_id}`.")
        return factory(project_root, config)

    def available_ids(self) -> list[str]:
        return list(ADAPTER_PRIORITY)


_REGISTRY = AdapterRegistry()


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _dummy_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    create_outputs = bool(config.get("create_outputs", True))
    return DummyAdapter(project_root, create_outputs=create_outputs)


def _claude_code_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    import shutil
    claude_bin = str(config.get("claude_bin", "claude"))
    if shutil.which(claude_bin) is None:
        raise AdapterRegistryError(
            f"claude_code adapter requires the `{claude_bin}` binary on PATH. "
            "Install Claude Code: https://docs.claude.com/en/docs/claude-code"
        )
    from forge_os.adapters.claude_code.adapter import ClaudeCodeAdapter
    model = config.get("model")
    permission_mode = config.get("permission_mode")
    return ClaudeCodeAdapter(
        project_root=project_root,
        claude_bin=claude_bin,
        model=str(model) if model else None,
        permission_mode=str(permission_mode) if permission_mode else None,
    )


def _claude_raw_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    try:
        from forge_os.adapters.bridge import AsyncToSyncBridge
        from forge_os.adapters.claude_raw.adapter import ClaudeRawAdapter
    except ImportError as exc:
        raise AdapterRegistryError(
            "claude_raw adapter requires 'anthropic>=0.40'. "
            "Install it with: pip install 'forge-os[claude-raw]'"
        ) from exc
    inner = ClaudeRawAdapter(
        api_key=str(config.get("api_key", "")) or None,
        default_model=str(config.get("model", "claude-opus-4-7")),
    )
    return AsyncToSyncBridge(inner)


def _claude_sdk_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    try:
        from forge_os.adapters.bridge import AsyncToSyncBridge
        from forge_os.adapters.claude_sdk.adapter import ClaudeSDKAdapter
    except ImportError as exc:
        raise AdapterRegistryError(
            "claude_sdk adapter requires 'claude-agent-sdk>=0.1.81'. "
            "Install it with: pip install 'forge-os[claude-sdk]'"
        ) from exc
    inner = ClaudeSDKAdapter(
        api_key=str(config.get("api_key", "")) or None,
        default_model=str(config.get("model", "claude-opus-4-7")),
    )
    return AsyncToSyncBridge(inner)


def _human_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    from forge_os.adapters.bridge import AsyncToSyncBridge
    from forge_os.adapters.human.adapter import HumanAdapter
    inner = HumanAdapter(show_thinking=bool(config.get("show_thinking", True)))
    return AsyncToSyncBridge(inner)


def _codex_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    import shutil
    if shutil.which("codex") is None:
        raise AdapterRegistryError(
            "codex adapter requires the `codex` binary on PATH. "
            "Install it with: npm i -g @openai/codex"
        )
    from forge_os.adapters.bridge import AsyncToSyncBridge
    from forge_os.adapters.codex.adapter import CodexAdapter
    inner = CodexAdapter(
        default_model=str(config.get("model", "gpt-5.4")),
        execution_boundary=str(config.get("execution_boundary", "kernel")),
    )
    return AsyncToSyncBridge(inner)


def _openclaw_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    gateway_command_raw = config.get("gateway_command")
    gateway_command = (
        [str(part) for part in gateway_command_raw]
        if isinstance(gateway_command_raw, (list, tuple)) and gateway_command_raw
        else None
    )
    # Only the stdio ACP transport (gateway_command) is wired in v0.1. Reject any
    # other config so `forge adapter status` reports openclaw unavailable rather than
    # constructing an adapter that cannot actually run.
    if not gateway_command:
        raise AdapterRegistryError(
            "openclaw adapter requires a configured `gateway_command` (stdio ACP "
            "transport); no gateway endpoint is configured. OpenClaw is optional — the "
            "HTTP/WebSocket transport is deferred to P11.08. "
            "See plan/OPENCLAW_ADAPTER_ARCHITECTURE.md."
        )
    from forge_os.adapters.bridge import AsyncToSyncBridge
    from forge_os.adapters.openclaw.adapter import OpenClawAdapter
    inner = OpenClawAdapter(
        gateway_command=gateway_command,
        default_model=str(config.get("model", "claude-opus-4-7")),
        forge_dir=project_root / ".forge",
    )
    return AsyncToSyncBridge(inner)


def _opencode_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    try:
        from forge_os.adapters.bridge import AsyncToSyncBridge
        from forge_os.adapters.opencode.adapter import OpenCodeAdapter
    except ImportError as exc:
        raise AdapterRegistryError(
            "opencode adapter requires 'opencode-ai>=1.14'. "
            "Install it with: pip install 'forge-os[opencode]'"
        ) from exc
    inner = OpenCodeAdapter(
        server_url=str(config.get("server_url", "http://localhost:4096")),
        server_password=str(config.get("server_password", "")) or None,
        auto_spawn_server=bool(config.get("auto_spawn_server", False)),
    )
    return AsyncToSyncBridge(inner)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_REGISTRY.register("dummy", _dummy_factory)
_REGISTRY.register("claude_code", _claude_code_factory)
_REGISTRY.register("claude_raw", _claude_raw_factory)
_REGISTRY.register("claude_sdk", _claude_sdk_factory)
_REGISTRY.register("human", _human_factory)
_REGISTRY.register("codex", _codex_factory)
_REGISTRY.register("openclaw", _openclaw_factory)
_REGISTRY.register("opencode", _opencode_factory)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_adapter_registry() -> AdapterRegistry:
    """Return the process-local adapter registry."""
    return _REGISTRY


def create_adapter_from_config(
    project_root: Path,
    config: ForgeConfig,
    *,
    event_store: EventStore | None = None,
) -> KernelAdapter:
    """Create the selected adapter from `.forge/config.yaml`.

    When `event_store` is provided it is bound to the adapter so spawn
    lifecycle/cost events are recorded on the production path (F0). Adapters
    that do not record ignore it (`bind_event_store` is a no-op).
    """
    adapter_id = config.default_adapter
    adapter_config = config.adapters.get(adapter_id, {})
    enabled = adapter_config.get("enabled", adapter_id == "dummy")
    if not enabled:
        raise AdapterRegistryError(f"Configured default adapter `{adapter_id}` is disabled.")
    adapter = get_adapter_registry().create(adapter_id, project_root, adapter_config)
    if event_store is not None:
        adapter.bind_event_store(event_store)
    return adapter


def adapter_placeholder_config() -> dict[str, dict[str, object]]:
    """Return default config placeholders in selected priority order."""
    return {
        aid: {
            "enabled": aid == "dummy",
            "implementation": ADAPTER_CLASS_NAMES[aid],
            "phase": "05" if aid == "dummy" else "05.5",
        }
        for aid in ADAPTER_PRIORITY
    }
