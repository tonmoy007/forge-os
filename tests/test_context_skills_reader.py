"""Tests for the domain-level read-only skill reader (P10.15)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from forge_os.context.skills_reader import SkillReader


def write_skill(
    forge_dir: Path,
    name: str,
    *,
    status: str = "installed",
    description: str | None = None,
) -> Path:
    skills_dir = forge_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    path = skills_dir / f"{name}.yaml"
    record = {
        "name": name,
        "description": description if description is not None else f"{name} skill",
        "status": status,
        "project_path": "/tmp/demo",
        "patterns": ["pattern-a"],
    }
    _ = path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


def test_list_records_returns_empty_when_skills_dir_missing(tmp_path: Path) -> None:
    reader = SkillReader(forge_dir=tmp_path / "forge")

    assert reader.list_records() == []


def test_list_records_parses_every_yaml_record(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha", status="installed")
    _ = write_skill(forge_dir, "beta", status="proposed")

    records = SkillReader(forge_dir=forge_dir).list_records()

    assert [record["name"] for record in records] == ["alpha", "beta"]
    assert records[0]["status"] == "installed"
    assert records[0]["patterns"] == ["pattern-a"]


def test_list_records_skips_invalid_yaml_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha")
    _ = (forge_dir / "skills" / "broken.yaml").write_text("name: [unclosed", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="forge.context.skills_reader"):
        records = SkillReader(forge_dir=forge_dir).list_records()

    assert [record["name"] for record in records] == ["alpha"]
    assert "Skipping malformed skill record" in caplog.text


def test_list_records_skips_non_mapping_yaml_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha")
    _ = (forge_dir / "skills" / "listy.yaml").write_text("- one\n- two\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="forge.context.skills_reader"):
        records = SkillReader(forge_dir=forge_dir).list_records()

    assert [record["name"] for record in records] == ["alpha"]
    assert "not a YAML mapping" in caplog.text


def test_list_records_ignores_non_yaml_files(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha")
    _ = (forge_dir / "skills" / "notes.txt").write_text("not a skill", encoding="utf-8")

    records = SkillReader(forge_dir=forge_dir).list_records()

    assert [record["name"] for record in records] == ["alpha"]


def test_get_returns_full_record_by_name(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha", description="does alpha things")

    record = SkillReader(forge_dir=forge_dir).get("alpha")

    assert record is not None
    assert record["description"] == "does alpha things"


def test_get_returns_none_for_unknown_name(tmp_path: Path) -> None:
    forge_dir = tmp_path / "forge"
    _ = write_skill(forge_dir, "alpha")

    assert SkillReader(forge_dir=forge_dir).get("missing") is None
