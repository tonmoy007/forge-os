"""Golden gate-evaluation dataset (P12.10).

A deterministic corpus of gate criteria + project states with known verdicts,
covering every gate type the GateCoordinator supports (required_file, pattern,
external_command, metric_threshold) and the severity->warn downgrade. Pins the
evaluator's pass / fail / warn behavior so a regression in any checker is caught.

A parametrized table is used instead of a tree of fixture directories: the
dataset is version-controlled and reviewable in one place, and each case is
self-contained and deterministic.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from forge_os.gates.coordinator import GateCoordinator
from forge_os.gates.models import GateCriterion


def _write(root: Path, name: str, content: str) -> None:
    _ = (root / name).write_text(content, encoding="utf-8")


def _noop(root: Path) -> None:
    pass


# (case_id, GateCriterion kwargs, setup(root), expected_status)
_GOLDEN: list[tuple[str, dict, Callable[[Path], None], str]] = [
    # ── passing ──────────────────────────────────────────────────────────────
    (
        "required_file/pass",
        {"id": "rf", "name": "rf", "type": "required_file", "criteria": {"path": "SRS.md"}},
        lambda r: _write(r, "SRS.md", "# requirements\n"),
        "pass",
    ),
    (
        "pattern/pass",
        {"id": "pt", "name": "pt", "type": "pattern",
         "criteria": {"path": "SRS.md", "pattern": r"## Goals"}},
        lambda r: _write(r, "SRS.md", "# requirements\n## Goals\n"),
        "pass",
    ),
    (
        "external_command/pass",
        {"id": "ec", "name": "ec", "type": "external_command", "criteria": {"command": ["true"]}},
        _noop,
        "pass",
    ),
    (
        "metric_threshold/pass",
        {"id": "mt", "name": "mt", "type": "metric_threshold",
         "criteria": {"metric_file": "metrics.json", "metric_key": "coverage",
                      "threshold": 0.8, "operator": ">="}},
        lambda r: _write(r, "metrics.json", json.dumps({"coverage": 0.9})),
        "pass",
    ),
    # ── failing (blocking severity) ──────────────────────────────────────────
    (
        "required_file/fail",
        {"id": "rf", "name": "rf", "type": "required_file", "criteria": {"path": "SRS.md"}},
        _noop,
        "fail",
    ),
    (
        "pattern/fail",
        {"id": "pt", "name": "pt", "type": "pattern",
         "criteria": {"path": "SRS.md", "pattern": r"## Goals"}},
        lambda r: _write(r, "SRS.md", "# requirements only\n"),
        "fail",
    ),
    (
        "external_command/fail",
        {"id": "ec", "name": "ec", "type": "external_command", "criteria": {"command": ["false"]}},
        _noop,
        "fail",
    ),
    (
        "metric_threshold/fail",
        {"id": "mt", "name": "mt", "type": "metric_threshold",
         "criteria": {"metric_file": "metrics.json", "metric_key": "coverage",
                      "threshold": 0.8, "operator": ">="}},
        lambda r: _write(r, "metrics.json", json.dumps({"coverage": 0.5})),
        "fail",
    ),
    # ── warning (failing condition downgraded by severity=warning) ───────────
    (
        "required_file/warn",
        {"id": "rf", "name": "rf", "type": "required_file", "severity": "warning",
         "criteria": {"path": "SRS.md"}},
        _noop,
        "warn",
    ),
    (
        "pattern/warn",
        {"id": "pt", "name": "pt", "type": "pattern", "severity": "warning",
         "criteria": {"path": "SRS.md", "pattern": r"## Goals"}},
        lambda r: _write(r, "SRS.md", "# requirements only\n"),
        "warn",
    ),
]


@pytest.mark.parametrize(
    "case_id,gate_kwargs,setup,expected", _GOLDEN, ids=[case[0] for case in _GOLDEN]
)
def test_gate_golden_verdicts(
    tmp_path: Path,
    case_id: str,
    gate_kwargs: dict,
    setup: Callable[[Path], None],
    expected: str,
) -> None:
    setup(tmp_path)
    gate = GateCriterion(**gate_kwargs)

    result = GateCoordinator(tmp_path).evaluate_gate(gate)

    assert result.status == expected, f"{case_id}: {result.summary}"
