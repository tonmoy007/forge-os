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
    AdapterRegistryError,
    PlaceholderAdapter,
    get_adapter_registry,
)
from forge_os.config.loader import load_config
from forge_os.config.writer import save_config
from forge_os.schemas.config import ForgeConfig


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


@dataclass
class AdapterMutation:
    """Result of toggling an adapter's enabled/default state in config."""

    adapter_id: str
    enabled: bool
    is_default: bool
    available: bool
    reason: str
    changed: bool


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

    def set_enabled(
        self, adapter_id: str, *, enabled: bool, make_default: bool = False
    ) -> AdapterMutation:
        """Enable/disable an adapter (and optionally make it the default kernel).

        Realizes FR-KA-003 — "user switches kernels by config change" — without
        hand-editing `.forge/config.yaml`. The write round-trips through the schema
        and is atomic. Raises ``AdapterRegistryError`` for an unknown id or an
        attempt to disable the adapter that is currently the default.
        """
        if adapter_id not in ADAPTER_PRIORITY:
            known = ", ".join(ADAPTER_PRIORITY)
            raise AdapterRegistryError(f"Unknown adapter `{adapter_id}`. Known adapters: {known}.")

        config = load_config(self._config_path)
        if not enabled and adapter_id == config.default_adapter:
            raise AdapterRegistryError(
                f"Cannot disable `{adapter_id}` while it is the default adapter. "
                "Set another adapter as default first: `forge adapter enable <id> --default`."
            )
        # Selecting an adapter as default is meaningless unless it is also enabled.
        if make_default:
            enabled = True

        data = config.model_dump(mode="json")
        adapters: dict[str, dict[str, object]] = data.setdefault("adapters", {})
        entry = adapters.get(adapter_id)
        if entry is None:
            # A hand-trimmed config may omit a known adapter; re-materialize its row.
            entry = {"implementation": ADAPTER_CLASS_NAMES[adapter_id]}
            adapters[adapter_id] = entry
        was_enabled = bool(entry.get("enabled", adapter_id == "dummy"))
        was_default = data.get("default_adapter") == adapter_id
        entry["enabled"] = enabled
        if make_default:
            data["default_adapter"] = adapter_id

        validated = ForgeConfig.model_validate(data)
        changed = (was_enabled != enabled) or (make_default and not was_default)
        if changed:
            save_config(self._config_path, validated)

        registry = get_adapter_registry()
        adapter_config = validated.adapters.get(adapter_id, {})
        available, reason, _capabilities = self._probe(registry, adapter_id, adapter_config)
        return AdapterMutation(
            adapter_id=adapter_id,
            enabled=enabled,
            is_default=validated.default_adapter == adapter_id,
            available=available,
            reason=reason,
            changed=changed,
        )

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
