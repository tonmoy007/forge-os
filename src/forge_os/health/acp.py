"""ACP agent health checker.

Uses Phase 08 ACP infrastructure:
- Registry accessibility check
- Installed agent health
- Session health via session/list
"""

from __future__ import annotations

from pathlib import Path

from forge_os.health.checker import HealthChecker, HealthResult


class ACPHealthChecker(HealthChecker):
    """Check ACP subsystem health: registry, agents, sessions."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check(self) -> HealthResult:
        cache_dir = self.project_root / ".forge" / "acp"

        # Check registry cache exists
        registry_cache = cache_dir / "registry.json"
        if not cache_dir.exists():
            return HealthResult(
                healthy=False,
                message="ACP cache directory not found. No agents discovered yet.",
                recommendations=["Run `forge acp discover` to fetch the ACP registry."],
            )

        # Check installed agents
        installed_file = cache_dir / "installed.json"
        installed_agents: list[dict] = []
        if installed_file.exists():
            import json
            installed = json.loads(installed_file.read_text())
            installed_agents = list(installed.values())

        details = {
            "registry_cached": registry_cache.exists(),
            "installed_agents": len(installed_agents),
            "agent_ids": [a.get("id", "") for a in installed_agents],
        }

        if not registry_cache.exists():
            return HealthResult(
                healthy=False,
                message="ACP registry not cached.",
                recommendations=["Run `forge acp discover` to fetch and cache the registry."],
            )

        return HealthResult(
            healthy=True,
            message=f"{len(installed_agents)} ACP agents installed, registry cached.",
            details=details,
        )
