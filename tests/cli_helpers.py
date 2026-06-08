"""Shared CLI test helpers.

Provides ``isolated_filesystem`` — an owned replacement for Click's
``CliRunner.isolated_filesystem``, deprecated in Click 8.2 and absent from the
click vendored by Typer >= 0.26. Each enclosed block runs with the working
directory set to a fresh temporary directory, matching the L001 ``tmp_path``
isolation rule (no test touches another test's filesystem state).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import Iterator


@contextlib.contextmanager
def isolated_filesystem() -> Iterator[str]:
    """Run the enclosed block with cwd set to a fresh temporary directory."""
    prev_cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp(prefix="forge-clitest-")
    os.chdir(tmp_dir)
    try:
        yield tmp_dir
    finally:
        os.chdir(prev_cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)
