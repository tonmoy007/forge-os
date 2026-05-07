"""Deterministic gate coordinator for Phase 04."""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter

from forge_os.events.bus import EventBus
from forge_os.events.model import new_event, utc_now
from forge_os.gates.loader import load_gate_file
from forge_os.gates.models import GateCriterion, GateResult


class GateEvaluationError(RuntimeError):
    """Raised when gate evaluation fails unexpectedly."""


class GateCoordinator:
    """Load, evaluate, and report Phase 04 gate criteria."""

    def __init__(self, project_root: Path, event_bus: EventBus | None = None) -> None:
        self.project_root: Path = project_root.resolve()
        self.gate_file: Path = self.project_root / "pipeline" / "gates.yaml"
        self.event_bus: EventBus | None = event_bus

    def load_gates(self) -> list[GateCriterion]:
        """Load gates from the active project."""

        return load_gate_file(self.gate_file)

    def gates_for_stage(self, stage_id: str) -> list[GateCriterion]:
        """Return enabled gates for a stage in deterministic order."""

        return sorted(
            (
                gate
                for gate in self.load_gates()
                if gate.enabled and (gate.stage_id is None or gate.stage_id == stage_id)
            ),
            key=lambda gate: gate.id,
        )

    def evaluate_stage(self, stage_id: str) -> list[GateResult]:
        """Evaluate enabled gates for a stage."""

        self._emit("GateStarted", stage_id, {"stage_id": stage_id})
        results = [self.evaluate_gate(gate) for gate in self.gates_for_stage(stage_id)]
        self._emit(
            "GateCompleted",
            stage_id,
            {
                "stage_id": stage_id,
                "blocking_failed": any(result.blocking for result in results),
                "result_count": len(results),
            },
        )
        return results

    def evaluate_gate(self, gate: GateCriterion) -> GateResult:
        """Evaluate one gate criterion."""

        started = utc_now()
        start_time = perf_counter()
        try:
            if gate.type == "required_file":
                status, summary, fix_hint, details = self._check_required_file(gate)
            elif gate.type == "pattern":
                status, summary, fix_hint, details = self._check_pattern(gate)
            else:
                status = "error"
                summary = f"Unsupported gate type `{gate.type}`."
                fix_hint = "Use a supported gate type: required_file or pattern."
                details = {}
        except Exception as exc:  # noqa: BLE001 - normalize checker failures
            status = "error"
            summary = f"Gate `{gate.id}` errored: {exc}"
            fix_hint = "Inspect the gate criteria and project files."
            details = {"error": str(exc)}

        if status == "fail" and gate.severity in {"warning", "advisory"}:
            status = "warn" if gate.severity == "warning" else "skipped"

        duration_ms = int((perf_counter() - start_time) * 1000)
        return GateResult(
            gate_id=gate.id,
            stage_id=gate.stage_id,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            details=details,
            started_at=started,
            finished_at=utc_now(),
            duration_ms=duration_ms,
            blocking=status in {"fail", "error"} and gate.severity == "blocking",
            fix_hint=fix_hint,
            metadata={"severity": gate.severity, "type": gate.type},
        )

    def has_blocking_failures(self, results: list[GateResult]) -> bool:
        """Return true if any result blocks progression."""

        return any(result.blocking for result in results)

    def render_report(self, results: list[GateResult]) -> str:
        """Render a readable gate report."""

        lines = ["# Forge Gate Report", ""]
        if not results:
            lines.append("No gates evaluated.")
            return "\n".join(lines) + "\n"

        for result in results:
            lines.append(f"## {result.gate_id}: {result.status}")
            lines.append("")
            lines.append(result.summary)
            if result.fix_hint:
                lines.append(f"Fix: {result.fix_hint}")
            lines.append(f"Blocking: {result.blocking}")
            lines.append("")
        return "\n".join(lines)

    def _check_required_file(
        self,
        gate: GateCriterion,
    ) -> tuple[str, str, str | None, dict[str, object]]:
        path_value = gate.criteria.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            return "error", f"Gate `{gate.id}` requires criteria.path.", None, {}

        target = self.project_root / path_value
        if target.is_file():
            return "pass", f"Required file exists: {path_value}", None, {"path": path_value}
        return (
            "fail",
            f"Required file is missing: {path_value}",
            f"Create `{path_value}` before completing this stage.",
            {"path": path_value},
        )

    def _check_pattern(
        self,
        gate: GateCriterion,
    ) -> tuple[str, str, str | None, dict[str, object]]:
        path_value = gate.criteria.get("path")
        pattern_value = gate.criteria.get("pattern")
        if not isinstance(path_value, str) or not path_value.strip():
            return "error", f"Gate `{gate.id}` requires criteria.path.", None, {}
        if not isinstance(pattern_value, str) or not pattern_value:
            return "error", f"Gate `{gate.id}` requires criteria.pattern.", None, {}

        target = self.project_root / path_value
        if not target.is_file():
            return (
                "fail",
                f"Pattern file is missing: {path_value}",
                f"Create `{path_value}` and include pattern `{pattern_value}`.",
                {"path": path_value, "pattern": pattern_value},
            )

        content = target.read_text(encoding="utf-8")
        if re.search(pattern_value, content, flags=re.MULTILINE):
            return (
                "pass",
                f"Pattern `{pattern_value}` found in {path_value}",
                None,
                {"path": path_value, "pattern": pattern_value},
            )
        return (
            "fail",
            f"Pattern `{pattern_value}` not found in {path_value}",
            f"Update `{path_value}` so it matches `{pattern_value}`.",
            {"path": path_value, "pattern": pattern_value},
        )

    def _emit(self, event_type: str, stage_id: str, payload: dict[str, object]) -> None:
        if self.event_bus is None:
            return
        event = new_event(
            event_type,  # type: ignore[arg-type]
            stage_id=stage_id,
            actor_type="core",
            actor_id="gate-coordinator",
            payload=payload,
        )
        _ = self.event_bus.emit(event)
