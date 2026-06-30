"""Phase 09 health check use cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.health.acp import ACPHealthChecker
from forge_os.health.adg import ADGHealthChecker
from forge_os.health.gates import GateHealthChecker
from forge_os.health.hook_latency import HookLatencyHealthChecker
from forge_os.health.memory import MemoryHealthChecker
from forge_os.health.state import StateHealthChecker


class HealthUseCases:
    """Aggregate health checks across all subsystems."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def run_full_check(self) -> dict[str, dict[str, Any]]:
        """Run all health checks and return a dict of subsystem -> result."""
        checkers = {
            "state": StateHealthChecker(self.project_root),
            "gates": GateHealthChecker(self.project_root),
            "adg": ADGHealthChecker(self.project_root),
            "memory": MemoryHealthChecker(self.project_root),
            "acp": ACPHealthChecker(self.project_root),
            "hook_latency": HookLatencyHealthChecker(self.project_root),
        }

        report: dict[str, dict[str, Any]] = {}
        for name, checker in checkers.items():
            try:
                result = checker.check()
                report[name] = {
                    "healthy": result.healthy,
                    "message": result.message,
                    "details": result.details,
                    "recommendations": result.recommendations,
                }
            except Exception as exc:
                report[name] = {
                    "healthy": False,
                    "message": f"Checker crashed: {exc}",
                    "details": {},
                    "recommendations": [],
                }

        return report
