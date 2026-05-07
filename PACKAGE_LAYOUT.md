# Forge OS Package Layout

Status: Phase 00 foundation decision.

This document defines the intended repository, package, and module layout for Forge OS. It is a design contract for Phase 01+ implementation and does not introduce runtime behavior by itself.

## Runtime and Packaging Decisions

- Runtime: Python 3.11+.
- Project metadata format: PEP 621 via `pyproject.toml` when the package scaffold is created.
- Initial installation mode: local editable package for development.
- User-facing installation path after packaging stabilizes: `pipx install forge-os` or equivalent package name.
- Standalone binaries: deferred until after the local Python package is stable.
- Development package manager: `uv` is preferred for fast, reproducible local development, while standard `pip` workflows must remain possible.
- Test runner: `pytest`.
- CLI framework: `typer`.
- Terminal output: `rich`.
- Schema validation: `pydantic`.
- YAML support: `pyyaml` initially; `ruamel.yaml` may be considered later if comment-preserving writes become necessary.
- Graph support: `networkx` for GraphML-compatible ADG operations in later phases.

## Initial Repository Layout

The Phase 01 implementation should introduce this structure incrementally:

| Path | Purpose | First Phase |
|---|---|---|
| `pyproject.toml` | Python package metadata and tool configuration | Phase 01 |
| `src/forge_os/` | Main Python package | Phase 01 |
| `src/forge_os/__init__.py` | Package marker and version export | Phase 01 |
| `src/forge_os/cli/` | CLI entry points and command modules | Phase 01 |
| `src/forge_os/config/` | Config loading, defaults, validation | Phase 01 |
| `src/forge_os/project/` | Forge project discovery and file layout helpers | Phase 01 |
| `src/forge_os/schemas/` | Pydantic models matching `SCHEMAS.md` | Phase 01+ |
| `src/forge_os/core/` | Deterministic orchestration and state ownership | Phase 02 |
| `src/forge_os/pipeline/` | Stage profiles, transitions, pipeline definitions | Phase 02 |
| `src/forge_os/events/` | Event bus and lifecycle events | Phase 03 |
| `src/forge_os/hooks/` | Hook loading and execution policy | Phase 03 |
| `src/forge_os/gates/` | Gate definitions, runners, reports | Phase 04 |
| `src/forge_os/adapters/` | Kernel adapter interface and implementations | Phase 05 |
| `src/forge_os/agents/` | Agent personas and output contracts | Phase 05 |
| `src/forge_os/memory/` | Reflections, lessons, memory operations | Phase 06 |
| `src/forge_os/graphs/` | ADG and graph persistence operations | Phase 07 |
| `src/forge_os/context/` | Context building and pruning | Phase 07 |
| `src/forge_os/backtrack/` | Backtrack tickets and rework flows | Phase 08 |
| `src/forge_os/security/` | Tool policy, approvals, audit logging | Phase 08 |
| `src/forge_os/health/` | Health checks and diagnostics | Phase 09 |
| `src/forge_os/daemon/` | Optional background daemon | Phase 10 |
| `src/forge_os/channels/` | Optional channel adapters | Phase 11 |
| `src/forge_os/plugins/` | Optional extension system | Phase 11 |
| `tests/` | Automated tests | Phase 01 |
| `docs/` | User/developer docs, later if needed | Phase 01+ |
| `adr/` | Formal Architecture Decision Records | Phase 00 |

## Import Boundary Rules

- `forge_os.core` may depend on schemas, config, pipeline, events, gates, security interfaces, and adapter interfaces.
- `forge_os.core` must not import concrete provider SDKs or concrete AI adapters.
- Concrete adapters live under `forge_os.adapters.<provider>` or later plugin packages.
- Provider-specific dependencies must be optional extras, not core dependencies.
- `forge_os.cli` may call application services, but it must not mutate Forge state directly.
- State writes must be performed only through core/state services.
- Hooks and plugins must not bypass state ownership.

## Suggested Package Extras

The eventual `pyproject.toml` should keep optional integrations out of the core install:

| Extra | Purpose |
|---|---|
| `dev` | Test, lint, type-check, docs tooling |
| `claude` | Claude Code adapter dependencies, if any |
| `codex` | OpenAI/Codex adapter dependencies |
| `openclaw` | OpenClaw HTTP/WebSocket client dependencies |
| `local-llm` | Local model runtime dependencies |
| `all-adapters` | Convenience extra for all non-core adapters |

## Naming Decision

Use Python package name `forge_os` to avoid ambiguity with the built-in concept of a forge and to comply with Python import naming conventions.

The CLI command should be `forge` unless package index conflicts force a different command name. If conflict occurs, record the deviation in a new ADR before changing the user-facing command.

## Phase 01 Scaffold Rules

Phase 01 may create the minimal package scaffold required for `forge --help`, `forge init`, and `forge status` planning work.

Phase 01 must not implement future-phase state transitions, adapters, memory, ADG, daemon, OpenClaw, channels, or plugins except as interfaces/placeholders directly required by the CLI scaffold.
