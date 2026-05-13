from pathlib import Path
from typing import Any

from forge_os.gates.evaluator import GateEvaluator
from forge_os.gates.models import ExternalCommandGate, MetricThresholdGate
from forge_os.project.security_enforcer import SecurityEnforcer


class GateUseCases:
    """Encapsulates business logic for gate evaluation."""

    def __init__(
        self,
        project_root: Path,
        security_enforcer: SecurityEnforcer | None = None,
    ) -> None:
        self.project_root = project_root
        self.evaluator = GateEvaluator(project_root, security_enforcer)

    def evaluate_external_command_gate(self, gate_config: dict[str, Any]) -> dict[str, Any]:
        """Evaluates an external command gate and returns the result."""
        gate = ExternalCommandGate(**gate_config)
        return self.evaluator.evaluate_external_command(gate)

    def evaluate_metric_threshold_gate(self, gate_config: dict[str, Any]) -> dict[str, Any]:
        """Evaluates a metric threshold gate and returns the result."""
        gate = MetricThresholdGate(**gate_config)
        return self.evaluator.evaluate_metric_threshold(gate)