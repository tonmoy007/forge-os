"""Adapter-swap regression suite (P12.04).

The kernel-adapter boundary (ADR-005): the orchestration engine owns canonical
state; an adapter is an execution surface only. Swapping the adapter that runs a
stage must not change the canonical lifecycle state — only the recorded
execution surface (the agent-run record's adapter id) may differ.

The same srs stage is run through three adapters, all offline:
- DummyAdapter — fabricates its own deliverable;
- HumanAdapter — driven through the real AsyncToSyncBridge by a scripted (no
  terminal) operator who completes immediately, deliverable pre-staged;
- ClaudeCodeAdapter — subprocess mocked to a success stream, deliverable
  pre-staged.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from forge_os.adapters.bridge import AsyncToSyncBridge
from forge_os.adapters.human.adapter import HumanAdapter
from forge_os.agents.executor import run_stage_agent
from forge_os.core.state_manager import StateManager
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state

_ADAPTERS = ("dummy", "human", "claude_code")


def _scripted_human(script: list[str]) -> HumanAdapter:
    """A HumanAdapter wired to a fixed input sequence — no real terminal."""
    pending = iter(script)

    def _input(_prompt: str = "") -> str:
        try:
            return next(pending)
        except StopIteration as exc:
            raise EOFError("scripted input exhausted") from exc

    return HumanAdapter(input_fn=_input, print_fn=lambda *_: None)


def _canonical_state(root: Path) -> dict:
    """The adapter-independent lifecycle facts, with volatile run-specific fields
    (project_id, timestamps, event ids, gate timing) projected out."""
    state = load_state(root).model_dump()
    return {
        "schema_version": state["schema_version"],
        "profile": state["profile"],
        "current_stage_id": state["current_stage_id"],
        "stages": [
            {
                "stage_id": stage["stage_id"],
                "status": stage["status"],
                "blocked_reason": stage["blocked_reason"],
            }
            for stage in state["stages"]
        ],
    }


def _run_srs_stage(root: Path, adapter: str) -> str:
    """Init a minimal project, run + complete the srs stage through ``adapter``,
    and return the adapter id the run recorded."""
    default_adapter = "claude_code" if adapter == "claude_code" else "dummy"
    initialize_project(
        root, project_name="Demo", profile="minimal", default_adapter=default_adapter
    )

    if adapter == "dummy":
        record = run_stage_agent(root, load_state(root), "srs")

    elif adapter == "human":
        # The human operator does not write files — pre-stage the deliverable.
        _ = (root / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
        bridge = AsyncToSyncBridge(_scripted_human(["d"]))  # complete immediately
        with patch(
            "forge_os.agents.executor.create_adapter_from_config", return_value=bridge
        ):
            record = run_stage_agent(root, load_state(root), "srs")

    else:  # claude_code, subprocess mocked
        _ = (root / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
        stream = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "done",
                "usage": {},
                "total_cost_usd": 0.0,
            }
        )
        completed = type("P", (), {"stdout": stream, "stderr": "", "returncode": 0})()
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run", return_value=completed):
                record = run_stage_agent(root, load_state(root), "srs")

    StateManager.for_project(root).complete_stage("srs")
    return record.adapter


def test_canonical_lifecycle_state_is_identical_across_adapters(tmp_path: Path) -> None:
    for name in _ADAPTERS:
        _run_srs_stage(tmp_path / name, name)

    canonical = {name: _canonical_state(tmp_path / name) for name in _ADAPTERS}
    assert canonical["dummy"] == canonical["human"] == canonical["claude_code"]
    assert canonical["dummy"]["stages"][0] == {
        "stage_id": "srs",
        "status": "complete",
        "blocked_reason": None,
    }

    # Guard against a vacuous comparison: the raw per-run state really does differ
    # (each project has its own random project_id) — the projection is doing work.
    project_ids = {str(load_state(tmp_path / name).project_id) for name in _ADAPTERS}
    assert len(project_ids) == len(_ADAPTERS)


def test_each_swap_records_its_own_execution_surface(tmp_path: Path) -> None:
    recorded = {name: _run_srs_stage(tmp_path / name, name) for name in _ADAPTERS}

    assert recorded["dummy"] == "dummy"
    assert recorded["human"] == "bridge:human"
    assert recorded["claude_code"] == "claude-code"
