"""CLI tests for `forge plug` (FR-EXT-002), driving the real Typer app."""

from __future__ import annotations

import pytest
import yaml
from typer.testing import CliRunner

from forge_os.cli.main import app

runner = CliRunner()


def _make_ext(dir_path, *, name="demo-ext", signed=False):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "extension.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "version": "0.1.0",
                "extension_point": "gate_criteria",
                "entry_point": "pkg:Obj",
                "signed": signed,
            }
        ),
        encoding="utf-8",
    )
    return dir_path


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--name", "Demo", "--profile", "minimal"])
    assert result.exit_code == 0, result.output
    return tmp_path


def test_plug_list_empty(project):
    result = runner.invoke(app, ["plug", "list"])
    assert result.exit_code == 0
    assert "No extensions installed" in result.output


def test_plug_install_list_remove_roundtrip(project):
    src = _make_ext(project / "ext-src")
    install = runner.invoke(app, ["plug", "install", str(src), "--allow-unsigned"])
    assert install.exit_code == 0, install.output
    listing = runner.invoke(app, ["plug", "list"])
    assert "demo-ext" in listing.output
    remove = runner.invoke(app, ["plug", "remove", "demo-ext"])
    assert remove.exit_code == 0, remove.output


def test_plug_install_unsigned_without_flag_fails(project):
    src = _make_ext(project / "ext-src")
    result = runner.invoke(app, ["plug", "install", str(src)])
    assert result.exit_code == 1
    # Fail-closed end-to-end: nothing installed, nothing audited.
    listing = runner.invoke(app, ["plug", "list"])
    assert "No extensions installed" in listing.output
    from forge_os.project.security_audit import SecurityAuditLog

    actions = [entry.get("action") for entry in SecurityAuditLog(project).read_all()]
    assert "ExtensionUnsignedInstalled" not in actions


def test_plug_remove_missing_fails(project):
    result = runner.invoke(app, ["plug", "remove", "ghost"])
    assert result.exit_code == 1
