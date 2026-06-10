# Forge OS

**Forge OS** is a local-first, kernel-agnostic SDLC orchestration CLI. It drives a
deterministic 12-stage software lifecycle — requirements through release — with
enforced quality gates, artifact dependency tracking, replayable agent runs, and
a security-audited adapter boundary that can spawn real AI coding agents. All
state lives in your project directory; no server, no cloud dependency, no
telemetry.

The orchestration engine owns canonical state. AI providers, humans, and plugins
are *execution surfaces only* — swap kernels with a config change, never a code
change.

```bash
pip install -e .
forge init --adapter claude-code        # verifies the claude binary up front
forge agent run --stage srs             # real agent writes SRS.md, contract-checked
```

---

## Why

AI coding agents are powerful but unaccountable: no lifecycle, no gates, no
audit trail, no way to replay what happened. Forge OS puts a deterministic
orchestration layer *around* the agent: every spawn is validated against a
security profile, recorded to an append-only event store, checked against a
declared output contract, and registered in an artifact dependency graph.
The kernel (Claude Code, Codex, OpenCode, a human at a terminal…) is a
pluggable detail.

**Proof point:** `forge agent run --stage srs` with the Claude Code adapter
runs end-to-end today — persona → subprocess → agent-written `SRS.md` →
contract validation → artifact registration — with the full lifecycle recorded.

---

## Kernel Adapters

| Adapter | Backend | Status |
|---------|---------|--------|
| `dummy` | Deterministic stub (no AI) | ✅ working — default |
| `claude_code` | `claude` CLI subprocess, stream-json | ✅ working — verified against claude 2.1.x |
| `claude_raw` | Anthropic Messages API | ✅ implemented (`pip install .[claude-raw]`) |
| `claude_sdk` | Claude Agent SDK | ✅ implemented (`pip install .[claude-sdk]`) |
| `codex` | Codex app-server (JSON-RPC) | ✅ implemented (needs `codex` CLI) |
| `opencode` | OpenCode HTTP + SSE | ✅ implemented (`pip install .[opencode]`) |
| `human` | Terminal operator | ✅ implemented — zero dependencies |
| `openclaw`, `local_llm` | — | 🚧 placeholders |

Select a kernel at init (`forge init --adapter claude-code`) or later via
`default_adapter` in `.forge/config.yaml`. `forge adapter status` shows
availability, capabilities, and install hints for every adapter.

The `claude_code` adapter additionally supports: per-spawn event-store recording
with deterministic **replay** (`run_id` → identical handle, no subprocess),
`.claude/settings.json` hook lifecycle, a fail-closed **SecurityEnforcer**
pre-spawn gate audited to `.forge/security-audit.jsonl`, `--model`, and
`--permission-mode`.

---

## Quick Start

```bash
# Install (Python 3.11+)
pip install -e .

# Initialize a project (dummy adapter — works with no AI provider)
forge init --path ./my-project --name Demo
cd ./my-project
forge status

# Or initialize against the real Claude Code kernel
forge init --path ./my-project --adapter claude-code --permission-mode acceptEdits

# Run the current stage's agent (SRS stage writes SRS.md, checked by contract)
forge agent run --stage srs

# Walk the pipeline
forge stage list
forge stage advance

# Inspect everything
forge adapter status      # adapter availability + capabilities
forge gate report         # quality gates
forge events tail -n 20   # lifecycle event log
forge security audit      # security decisions
forge health check        # subsystem health
```

## Command Surface

`init` · `status` · `explain` plus sub-apps:
`config` (show, validate) · `stage` (list, start, complete, advance, override) ·
`events` (list, tail) · `gate` (list, check, report) · `adapter` (list, status) ·
`agent` (list, contracts, run) · `lesson` (list, add, approve, deprecate) ·
`reflection` (list, show) · `artifact` (list, register, refresh) ·
`context` (select) · `backtrack` (list, plan, approve, run) ·
`security` (audit) · `health` (check) · `acp` (discover, list, install, sessions, close-session)

---

## Architecture

Strict layering, enforced by pre-merge checks:

```
cli/  ──▶  use_cases/  ──▶  core/, gates/, project/, context/, memory/,
                            kernel/, events/, hooks/, agents/, adapters/
                                            │
                                            ▼
                                       schemas/   (pure Pydantic, zero internal imports)
```

- **`StateManager`** is the only writer of `.forge/state.json` — atomic writes,
  Pydantic-validated, every mutation appends a lifecycle event. A SQLite event
  store dual-writes alongside it (WAL mode), growing toward event-sourced
  authority.
- **`KernelAdapter`** is the portability boundary: the engine never imports a
  provider SDK. Async adapters plug into the sync engine through
  `AsyncToSyncBridge`; ACP-compatible agents plug in additively.
- **State never advances because an adapter, hook, or plugin failed.**

Deep dives: [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`BUILD_SPEC.md`](BUILD_SPEC.md) ·
[`SCHEMAS.md`](SCHEMAS.md) · ADRs in [`adr/`](adr/)

## Project Layout (created by `forge init`)

```
.forge/      config.yaml, state.json, events.jsonl, security-audit.jsonl,
             lessons.yaml, reflections/, agents/{personas,contracts}/
pipeline/    stages.yaml, gates.yaml, state.md (human-readable mirror), decisions/, log/
tasks/       task plans and notes
```

---

## Development

```bash
pip install -e .[dev]

python -m pytest                      # full suite (476 tests)
python -m ruff check src tests       # lint (E F I UP B, line length 100)
python -m compileall src tests       # syntax sweep
```

The reference environment is a clean `python:3.12-slim` container; CI
(`.github/workflows/ci.yml`) runs the same gate on every PR.

## Contributing

1. Read `plan/CURRENT_PHASE.md` for live status, then the relevant `plan/PHASE-XX-*.md`.
2. New CLI commands: domain logic in a domain module → use case in `use_cases/` →
   thin Typer sub-app in `cli/commands/` registered in `main.py`. CLI never
   imports domain modules directly.
3. Every module ships with a test file. No feature without tests; no bug fix
   without a regression test.
4. One logical task per commit, referencing the phase task ID.

---

## License

[Apache-2.0](LICENSE)
