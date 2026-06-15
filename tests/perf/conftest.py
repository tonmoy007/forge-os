"""Fixtures for the performance benchmark suite (``tests/perf``).

These benchmarks measure the SRS §5.1 NFR targets. They are marked ``perf`` and
deselected from the default run (see pyproject ``addopts``); run them with
``pytest tests/perf -m perf --benchmark-json=perf.json``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.project.scaffold import initialize_project


@pytest.fixture
def bench_project(tmp_path: Path) -> Path:
    """A freshly initialized minimal project with the srs deliverable in place,
    so stage/gate/context operations have realistic inputs to measure."""
    initialize_project(tmp_path, project_name="Bench", profile="minimal")
    _ = (tmp_path / "SRS.md").write_text("# Requirements\n", encoding="utf-8")
    return tmp_path
