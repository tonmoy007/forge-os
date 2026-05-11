# ADR-001 — Runtime and Packaging

Status: accepted

Date: Phase 00

## Context

Forge OS needs a runtime suitable for local-first CLI tooling, deterministic file operations, schema validation, graph processing, tests, and eventual optional integrations with AI runtimes and channels.

## Decision

Use Python 3.11+ as the implementation runtime.

Use a local Python package as the first distribution target. Use PEP 621 project metadata through `pyproject.toml` when the implementation scaffold is created.

Prefer `uv` for local development workflows while preserving standard `pip` compatibility. Support `pipx` installation once packaging stabilizes. Defer standalone binaries until later.

## Consequences

Positive:

- Strong CLI ecosystem through `typer` and `rich`.
- Strong validation support through `pydantic`.
- Strong test ecosystem through `pytest`.
- Mature filesystem, subprocess, JSON/YAML, and graph libraries.
- Easy local development and editable installs.

Tradeoffs:

- Standalone binary distribution requires additional packaging work later.
- Provider-specific integrations must be isolated in optional dependencies to avoid bloating core installs.

## Implementation Guidance

- Package import name: `forge_os`.
- Preferred CLI command: `forge`.
- Do not introduce provider dependencies as core dependencies.
- Phase 01 should create package scaffolding only as needed for CLI MVP work.
