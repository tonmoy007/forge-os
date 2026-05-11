"""Phase 05 adapter registry and config selection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from forge_os.adapters.base import BaseKernelAdapter, KernelAdapter
from forge_os.adapters.dummy import DummyAdapter
from forge_os.schemas.config import ForgeConfig

AdapterFactory = Callable[[Path, dict[str, object]], KernelAdapter]

ADAPTER_PRIORITY: tuple[str, ...] = (
    "dummy",
    "claude_code",
    "codex",
    "openclaw",
    "opencode",
    "local_llm",
    "human",
)

ADAPTER_CLASS_NAMES: dict[str, str] = {
    "dummy": "DummyAdapter",
    "claude_code": "ClaudeCodeAdapter",
    "codex": "CodexAdapter",
    "openclaw": "OpenClawAdapter",
    "opencode": "OpenCodeAdapter",
    "local_llm": "LocalLLMAdapter",
    "human": "HumanAdapter",
}


class AdapterRegistryError(RuntimeError):
    """Raised when adapter selection or construction fails."""


class PlaceholderAdapter(BaseKernelAdapter):
    """Configured placeholder for future adapters not implemented in Phase 05."""

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id

    def spawn_agent(self, persona, context, tools):  # type: ignore[no-untyped-def]
        class_name = ADAPTER_CLASS_NAMES.get(self.adapter_id, self.adapter_id)
        raise AdapterRegistryError(f"{class_name} is configured but not implemented in Phase 05.")


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


def _dummy_factory(project_root: Path, config: dict[str, object]) -> KernelAdapter:
    create_outputs = bool(config.get("create_outputs", True))
    return DummyAdapter(project_root, create_outputs=create_outputs)


_REGISTRY.register("dummy", _dummy_factory)


def get_adapter_registry() -> AdapterRegistry:
    """Return the process-local adapter registry."""

    return _REGISTRY


def create_adapter_from_config(project_root: Path, config: ForgeConfig) -> KernelAdapter:
    """Create the selected adapter from `.forge/config.yaml`."""

    adapter_id = config.default_adapter
    adapter_config = config.adapters.get(adapter_id, {})
    enabled = adapter_config.get("enabled", adapter_id == "dummy")
    if not enabled:
        raise AdapterRegistryError(f"Configured default adapter `{adapter_id}` is disabled.")
    return get_adapter_registry().create(adapter_id, project_root, adapter_config)


def adapter_placeholder_config() -> dict[str, dict[str, object]]:
    """Return default config placeholders in selected priority order."""

    return {
        adapter_id: {
            "enabled": adapter_id == "dummy",
            "implementation": ADAPTER_CLASS_NAMES[adapter_id],
            "phase": "05" if adapter_id == "dummy" else "future",
        }
        for adapter_id in ADAPTER_PRIORITY
    }
