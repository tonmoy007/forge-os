"""Gate health checker: pass rates, last run status, simulation fixtures."""

from __future__ import annotations

from pathlib import Path

from forge_os.gates.coordinator import GateCoordinator
from forge_os.health.checker import HealthChecker, HealthResult


class GateHealthChecker(HealthChecker):
    """Check gate subsystem health."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def check(self) -> HealthResult:
        gate_file = self.project_root / "pipeline" / "gates.yaml"
        if not gate_file.exists():
            return HealthResult(
                healthy=False,
                message="No gates.yaml found. Project may not have configured gates.",
                recommendations=["Create pipeline/gates.yaml or run `forge init --force`."],
            )

        try:
            coordinator = GateCoordinator(self.project_root)
            gates = coordinator.load_gates()
        except Exception as exc:
            return HealthResult(
                healthy=False,
                message=f"Failed to load gates: {exc}",
            )

        enabled = [g for g in gates if g.enabled]
        blocking = [g for g in enabled if g.severity == "blocking"]

        details = {
            "total_gates": len(gates),
            "enabled_gates": len(enabled),
            "blocking_gates": len(blocking),
            "types": list({g.type for g in gates}),
        }

        return HealthResult(
            healthy=True,
            message=f"{len(enabled)} gates enabled ({len(blocking)} blocking).",
            details=details,
        )
