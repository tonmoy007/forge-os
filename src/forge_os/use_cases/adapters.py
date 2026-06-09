"""Use cases for inspecting kernel adapters (Phase 05.5 Slice 4).

`forge adapter status` answers "which adapters can I actually select right now?"
by probing each one: an adapter is *available* if its factory constructs without
raising (e.g. the `claude` binary is on PATH, the optional dep is installed) and
is not a registered-but-unimplemented placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forge_os.adapters.registry import (
    ADAPTER_CLASS_NAMES,
    ADAPTER_PRIORITY,
    AdapterRegistry,
    PlaceholderAdapter,
    get_adapter_registry,
)
from forge_os.config.loader import load_config


@dataclass
class AdapterStatus:
    """Selectability snapshot for one kernel adapter."""

    adapter_id: str
    implementation: str
    enabled: bool
    is_default: bool
    available: bool
    reason: str
    capabilities: list[str]


class AdapterUseCases:
    """Inspect which kernel adapters are configured and actually selectable."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self._config_path = self.project_root / ".forge" / "config.yaml"

    def status(self) -> list[AdapterStatus]:
        """Return a selectability snapshot for every adapter, in priority order."""
        config = load_config(self._config_path)
        registry = get_adapter_registry()
        statuses: list[AdapterStatus] = []
        for adapter_id in ADAPTER_PRIORITY:
            adapter_config = config.adapters.get(adapter_id, {})
            enabled = bool(adapter_config.get("enabled", adapter_id == "dummy"))
            available, reason, capabilities = self._probe(registry, adapter_id, adapter_config)
            statuses.append(
                AdapterStatus(
                    adapter_id=adapter_id,
                    implementation=ADAPTER_CLASS_NAMES[adapter_id],
                    enabled=enabled,
                    is_default=adapter_id == config.default_adapter,
                    available=available,
                    reason=reason,
                    capabilities=capabilities,
                )
            )
        return statuses

    def _probe(
        self, registry: AdapterRegistry, adapter_id: str, adapter_config: dict[str, object]
    ) -> tuple[bool, str, list[str]]:
        """Try to construct the adapter; report (available, reason, capabilities)."""
        try:
            adapter = registry.create(adapter_id, self.project_root, adapter_config)
        except Exception as exc:  # noqa: BLE001
            # A status probe constructs every adapter; one factory failing
            # (missing binary, absent optional dep, bad config) must surface as
            # "unavailable: <reason>", never crash the whole report.
            return False, str(exc), []
        if isinstance(adapter, PlaceholderAdapter):
            return False, "not implemented", []
        capabilities = sorted(getattr(adapter, "optional_capabilities", frozenset()))
        return True, "", capabilities
