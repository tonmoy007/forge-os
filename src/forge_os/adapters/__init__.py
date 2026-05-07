"""Phase 05 kernel adapter support."""

from forge_os.adapters.base import AgentHandle, EventResponse, KernelAdapter, ToolList
from forge_os.adapters.dummy import DummyAdapter
from forge_os.adapters.registry import ADAPTER_PRIORITY, AdapterRegistry, create_adapter_from_config

__all__ = [
    "ADAPTER_PRIORITY",
    "AdapterRegistry",
    "AgentHandle",
    "DummyAdapter",
    "EventResponse",
    "KernelAdapter",
    "ToolList",
    "create_adapter_from_config",
]
