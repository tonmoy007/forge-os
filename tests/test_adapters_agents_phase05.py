from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from forge_os.adapters.registry import ADAPTER_PRIORITY, adapter_placeholder_config
from forge_os.agents.executor import AgentExecutionError, run_stage_agent
from forge_os.agents.loader import load_contracts, load_personas
from forge_os.cli.main import app
from forge_os.project.scaffold import initialize_project
from forge_os.project.status import load_state

runner = CliRunner()


def test_adapter_priority_matches_phase05_roadmap() -> None:
    assert ADAPTER_PRIORITY == (
        "dummy",
        "claude_code",
        "claude_raw",
        "claude_sdk",
        "codex",
        "openclaw",
        "opencode",
        "local_llm",
        "human",
    )

    placeholders = adapter_placeholder_config()
    assert list(placeholders) == list(ADAPTER_PRIORITY)
    assert placeholders["dummy"]["enabled"] is True
    assert placeholders["openclaw"]["enabled"] is False


def test_builtin_personas_and_contracts_cover_standard_stages(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="standard")

    personas = load_personas(tmp_path)
    contracts = load_contracts(tmp_path)

    stage_personas = [persona for persona in personas.values() if persona.category == "stage"]
    cross_stage_personas = [
        persona for persona in personas.values() if persona.category == "cross_stage"
    ]
    covered_stages = {stage_id for persona in stage_personas for stage_id in persona.stage_ids}

    assert len(stage_personas) == 12
    assert len(cross_stage_personas) == 4
    assert covered_stages == {
        "srs",
        "product",
        "architecture",
        "spec",
        "plan",
        "build",
        "eval",
        "deploy",
        "monitor",
        "feedback",
        "resolve",
        "release",
    }
    assert len(contracts) == 12


def test_dummy_adapter_runs_current_stage_and_persists_outputs(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    state = load_state(tmp_path)

    record = run_stage_agent(tmp_path, state, "srs")

    assert record.adapter == "dummy"
    assert record.status == "completed"
    assert record.contract is not None
    assert record.contract.passed is True
    assert (tmp_path / "SRS.md").exists()

    runs = (tmp_path / ".forge" / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(runs) == 1
    assert json.loads(runs[0])["persona_id"] == "requirements_analyst"


def test_missing_dummy_outputs_fail_output_contract(tmp_path: Path) -> None:
    _ = initialize_project(tmp_path, project_name="Demo", profile="minimal")
    config_path = tmp_path / ".forge" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["dummy"]["create_outputs"] = False
    _ = config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    state = load_state(tmp_path)

    try:
        _ = run_stage_agent(tmp_path, state, "srs")
    except AgentExecutionError as exc:
        assert "Required output is missing: SRS.md" in str(exc)
    else:
        raise AssertionError("Expected output contract failure")

    assert not (tmp_path / "SRS.md").exists()
    runs = (tmp_path / ".forge" / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(runs[0])["status"] == "contract_failed"


def test_agent_cli_run_enables_stage_advance() -> None:
    with runner.isolated_filesystem():
        init_result = runner.invoke(app, ["init", "--name", "Demo"])
        run_result = runner.invoke(app, ["agent", "run"])
        advance_result = runner.invoke(app, ["stage", "advance"])

        assert init_result.exit_code == 0, init_result.output
        assert run_result.exit_code == 0, run_result.output
        assert "requirements_analyst" in run_result.output
        assert advance_result.exit_code == 0, advance_result.output
        assert "build" in advance_result.output


def test_adapter_and_agent_cli_list_commands() -> None:
    with runner.isolated_filesystem():
        runner.invoke(app, ["init", "--name", "Demo", "--profile", "standard"])
        adapter_result = runner.invoke(app, ["adapter", "list"])
        agent_result = runner.invoke(app, ["agent", "list"])
        contract_result = runner.invoke(app, ["agent", "contracts"])

        assert adapter_result.exit_code == 0, adapter_result.output
        assert "DummyAdapter" in adapter_result.output
        assert "OpenClawAdapter" in adapter_result.output
        assert agent_result.exit_code == 0, agent_result.output
        assert "requirements_analyst" in agent_result.output
        assert "release_manager" in agent_result.output
        assert contract_result.exit_code == 0, contract_result.output
        assert "srs_outputs" in contract_result.output
