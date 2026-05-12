import json
import subprocess
import time
from pathlib import Path
from typing import Any

from forge_os.gates.models import ExternalCommandGate, MetricThresholdGate


class GateEvaluator:
    """Evaluates gates, including new external command and metric gates."""

    def __init__(self, project_root: Path, security_enforcer=None) -> None:
        self.project_root = project_root
        self.security_enforcer = security_enforcer

    def evaluate_external_command(self, gate: ExternalCommandGate) -> dict[str, Any]:
        """Executes a command and determines pass/fail based on exit code."""
        start_time = time.time()
        
        try:
            # Use security enforcer if available to run the command
            if self.security_enforcer:
                result = self.security_enforcer.run_command(
                    actor={"id": "gate_evaluator"}, 
                    command=gate.command, 
                    timeout=gate.timeout_seconds
                )
            else:
                result = subprocess.run(
                    gate.command,
                    capture_output=True,
                    text=True,
                    timeout=gate.timeout_seconds,
                    cwd=str(self.project_root)
                )
            
            status = "pass" if result.returncode == 0 else "fail"
            summary = f"Command exited with {result.returncode}"
            details = {"stdout": result.stdout, "stderr": result.stderr}
            
        except subprocess.TimeoutExpired:
            status = "error"
            summary = f"Command timed out after {gate.timeout_seconds}s"
            details = {}
        except Exception as e:
            status = "error"
            summary = str(e)
            details = {}

        return {
            "status": status,
            "summary": summary,
            "details": details,
            "duration_ms": int((time.time() - start_time) * 1000)
        }

    def evaluate_metric_threshold(self, gate: MetricThresholdGate) -> dict[str, Any]:
        """Parses a metric file and compares a value against a threshold."""
        start_time = time.time()
        
        try:
            file_path = self.project_root / gate.metric_file
            if not file_path.exists():
                return {
                    "status": "error",
                    "summary": f"Metric file {gate.metric_file} not found",
                    "details": {},
                    "duration_ms": 0
                }
            
            data = json.loads(file_path.read_text())
            value = data.get(gate.metric_key)
            
            if value is None:
                return {
                    "status": "error",
                    "summary": f"Metric key {gate.metric_key} not found in {gate.metric_file}",
                    "details": {},
                    "duration_ms": 0
                }
            
            # Comparison logic
            passed = False
            if gate.operator == ">=":
                passed = value >= gate.threshold
            elif gate.operator == ">":
                passed = value > gate.threshold
            elif gate.operator == "<=":
                passed = value <= gate.threshold
            elif gate.operator == "<":
                passed = value < gate.threshold
            elif gate.operator == "==":
                passed = value == gate.threshold

            status = "pass" if passed else "fail"
            summary = (
                f"Metric {gate.metric_key} is {value} "
                f"(Threshold {gate.operator} {gate.threshold})"
            )

        except Exception as e:
            status = "error"
            summary = str(e)

        return {
            "status": status,
            "summary": summary,
            "details": {},
            "duration_ms": int((time.time() - start_time) * 1000),
        }
