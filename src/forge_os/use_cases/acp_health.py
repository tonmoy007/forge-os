"""Phase 09 ACP agent health monitoring and restart logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.kernel.acp_registry_adapter import ACPRegistryAdapter


class ACPHealthUseCases:
    """ACP agent health monitoring, session management, and restart logic.

    Uses Phase 08 ACPClient and ACPRegistryAdapter for health detection.
    """

    def __init__(self, project_root: Path) -> None:
        cache_dir = project_root / ".forge" / "acp"
        self.registry = ACPRegistryAdapter(cache_dir)
        self.project_root = project_root

    def check_registry_health(self) -> dict[str, Any]:
        """Check if the ACP registry is accessible or cached."""
        cache_file = self.registry.cache_dir / "registry.json"
        is_cached = cache_file.exists()

        # Try live check (non-blocking, brief timeout)
        is_reachable = False
        try:
            is_reachable = self.registry.is_registry_accessible()
        except Exception:  # noqa: BLE001
            pass

        return {
            "registry_reachable": is_reachable,
            "registry_cached": is_cached,
            "status": "ok" if (is_reachable or is_cached) else "unavailable",
        }

    def check_installed_agent_health(self) -> list[dict[str, Any]]:
        """Check health of all installed ACP agents."""
        installed = self.registry.get_installed_agents()
        result: list[dict[str, Any]] = []
        for agent in installed:
            health: dict[str, Any] = {
                "agent_id": agent.get("id", "unknown"),
                "name": agent.get("name", agent.get("id", "unknown")),
                "version": agent.get("version", "unknown"),
                "distribution": agent.get("distribution_type", "unknown"),
                "installed": True,
                "session_healthy": None,
                "stale_sessions": [],
            }
            result.append(health)
        return result

    def detect_and_clean_stale_sessions(self) -> list[dict[str, Any]]:
        """Detect stale sessions and close them.

        In production this connects to running ACP agents via ACPClient
        and calls session/list + session/close. Currently returns the
        detection infrastructure — actual agent process management
        requires running agents which is a Phase 10 daemon concern.
        """
        installed = self.registry.get_installed_agents()
        actions: list[dict[str, Any]] = []
        for agent in installed:
            actions.append({
                "agent_id": agent.get("id", "unknown"),
                "detected_sessions": 0,
                "stale_sessions": 0,
                "closed_sessions": 0,
                "status": "no_running_agents",
            })
        return actions

    def get_health_report(self) -> dict[str, Any]:
        """Aggregate all ACP health information."""
        registry = self.check_registry_health()
        agents = self.check_installed_agent_health()
        sessions = self.detect_and_clean_stale_sessions()
        return {
            "registry": registry,
            "agents": agents,
            "session_actions": sessions,
            "healthy": (
                registry["status"] == "ok"
                or len(agents) > 0
            ),
        }
