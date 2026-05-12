"""Tests for Phase 08 gates: external command, metric threshold, coordinator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_os.gates.coordinator import GateCoordinator
from forge_os.gates.evaluator import GateEvaluator
from forge_os.gates.models import (
    ExternalCommandGate,
    GateCriterion,
    MetricThresholdGate,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "test-project"
    root.mkdir(parents=True)
    (root / "pipeline").mkdir()
    return root


@pytest.fixture
def evaluator(project_root: Path) -> GateEvaluator:
    return GateEvaluator(project_root)


@pytest.fixture
def coordinator(project_root: Path) -> GateCoordinator:
    return GateCoordinator(project_root)


@pytest.fixture
def metric_file(project_root: Path) -> Path:
    path = project_root / "metrics.json"
    path.write_text(json.dumps({"coverage": 85.0, "errors": 2, "loc": 5000}))
    return path


# ── ExternalCommandGate tests ────────────────────────────────────────────────


class TestGateEvaluatorExternalCommand:
    def test_command_success(self, evaluator: GateEvaluator) -> None:
        gate = ExternalCommandGate(
            id="cmd-test",
            name="Test Command",
            command=["echo", "hello"],
            timeout_seconds=10,
        )
        result = evaluator.evaluate_external_command(gate)
        assert result["status"] == "pass"
        assert "exited with 0" in result["summary"]

    def test_command_failure(self, evaluator: GateEvaluator) -> None:
        gate = ExternalCommandGate(
            id="cmd-fail",
            name="Failing Command",
            command=["sh", "-c", "exit 1"],
            timeout_seconds=10,
        )
        result = evaluator.evaluate_external_command(gate)
        assert result["status"] == "fail"

    def test_command_timeout(self, evaluator: GateEvaluator) -> None:
        gate = ExternalCommandGate(
            id="cmd-timeout",
            name="Timeout Test",
            command=["sleep", "10"],
            timeout_seconds=1,
        )
        result = evaluator.evaluate_external_command(gate)
        assert result["status"] == "error"
        assert "timed out" in result["summary"]

    def test_command_not_found(self, evaluator: GateEvaluator) -> None:
        gate = ExternalCommandGate(
            id="cmd-notfound",
            name="Not Found",
            command=["nonexistent_command_xyz"],
            timeout_seconds=5,
        )
        result = evaluator.evaluate_external_command(gate)
        assert result["status"] == "error"

    def test_command_stdout_captured(self, evaluator: GateEvaluator) -> None:
        gate = ExternalCommandGate(
            id="cmd-stdout",
            name="Stdout Test",
            command=["echo", "hello world"],
            timeout_seconds=5,
        )
        result = evaluator.evaluate_external_command(gate)
        assert result["details"]["stdout"].strip() == "hello world"


# ── MetricThresholdGate tests ────────────────────────────────────────────────


class TestGateEvaluatorMetricThreshold:
    def test_metric_passes_threshold(self, evaluator: GateEvaluator, metric_file: Path) -> None:
        gate = MetricThresholdGate(
            id="metric-pass",
            name="Coverage Check",
            metric_file="metrics.json",
            metric_key="coverage",
            threshold=80.0,
            operator=">=",
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "pass"

    def test_metric_fails_threshold(self, evaluator: GateEvaluator, metric_file: Path) -> None:
        gate = MetricThresholdGate(
            id="metric-fail",
            name="Error Limit",
            metric_file="metrics.json",
            metric_key="errors",
            threshold=1.0,
            operator="<=",
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "fail"

    def test_metric_file_not_found(self, evaluator: GateEvaluator) -> None:
        gate = MetricThresholdGate(
            id="metric-notfound",
            name="Missing File",
            metric_file="nonexistent.json",
            metric_key="coverage",
            threshold=80.0,
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "error"

    def test_metric_key_not_found(self, evaluator: GateEvaluator, project_root: Path) -> None:
        path = project_root / "empty.json"
        path.write_text(json.dumps({}))
        gate = MetricThresholdGate(
            id="metric-key-missing",
            name="Missing Key",
            metric_file="empty.json",
            metric_key="nonexistent",
            threshold=0.0,
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "error"

    def test_metric_exact_match(self, evaluator: GateEvaluator, project_root: Path) -> None:
        path = project_root / "exact.json"
        path.write_text(json.dumps({"value": 42}))
        gate = MetricThresholdGate(
            id="metric-exact",
            name="Exact Match",
            metric_file="exact.json",
            metric_key="value",
            threshold=42.0,
            operator="==",
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "pass"

    def test_metric_greater_than(self, evaluator: GateEvaluator, project_root: Path) -> None:
        path = project_root / "gt.json"
        path.write_text(json.dumps({"size": 100}))
        gate = MetricThresholdGate(
            id="metric-gt",
            name="Greater Than",
            metric_file="gt.json",
            metric_key="size",
            threshold=50.0,
            operator=">",
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "pass"

    def test_metric_less_than(self, evaluator: GateEvaluator, project_root: Path) -> None:
        path = project_root / "lt.json"
        path.write_text(json.dumps({"size": 10}))
        gate = MetricThresholdGate(
            id="metric-lt",
            name="Less Than",
            metric_file="lt.json",
            metric_key="size",
            threshold=20.0,
            operator="<",
        )
        result = evaluator.evaluate_metric_threshold(gate)
        assert result["status"] == "pass"


# ── GateCoordinator integration tests ────────────────────────────────────────


class TestGateCoordinatorPhase08:
    def test_coordinator_external_command_gate(
        self, coordinator: GateCoordinator, project_root: Path
    ) -> None:
        gate = GateCriterion(
            id="coord-cmd",
            name="Coordinator External Command",
            type="external_command",
            criteria={"command": ["echo", "gate-test"]},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status in ("pass", "error")
        assert result.gate_id == "coord-cmd"

    def test_coordinator_metric_threshold_gate(
        self, coordinator: GateCoordinator, project_root: Path
    ) -> None:
        (project_root / "coord-metrics.json").write_text(
            json.dumps({"score": 95.0})
        )
        gate = GateCriterion(
            id="coord-metric",
            name="Coordinator Metric",
            type="metric_threshold",
            criteria={
                "metric_file": "coord-metrics.json",
                "metric_key": "score",
                "threshold": 90.0,
                "operator": ">=",
            },
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "pass"
        assert result.gate_id == "coord-metric"

    def test_coordinator_unknown_gate_type(self, coordinator: GateCoordinator) -> None:
        gate = GateCriterion(
            id="coord-unknown",
            name="Unknown Type",
            type="nonexistent_type",
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "error"

    def test_existing_file_and_pattern_gates_still_work(
        self, coordinator: GateCoordinator, project_root: Path
    ) -> None:
        (project_root / "README.md").write_text("# Test Project\n")
        file_gate = GateCriterion(
            id="file-gate",
            name="Required File",
            type="required_file",
            criteria={"path": "README.md"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(file_gate)
        assert result.status == "pass"

        pattern_gate = GateCriterion(
            id="pattern-gate",
            name="Pattern",
            type="pattern",
            criteria={"path": "README.md", "pattern": "Test"},
            enabled=True,
        )
        result = coordinator.evaluate_gate(pattern_gate)
        assert result.status == "pass"

    def test_external_command_gate_missing_command(self, coordinator: GateCoordinator) -> None:
        gate = GateCriterion(
            id="cmd-no-command",
            name="No Command",
            type="external_command",
            criteria={},
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "error"

    def test_metric_threshold_gate_missing_file(self, coordinator: GateCoordinator) -> None:
        gate = GateCriterion(
            id="metric-no-file",
            name="No File",
            type="metric_threshold",
            criteria={
                "metric_key": "score",
                "threshold": 90.0,
            },
            enabled=True,
        )
        result = coordinator.evaluate_gate(gate)
        assert result.status == "error"
