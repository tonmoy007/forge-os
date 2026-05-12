# Forge OS

**Forge OS** is a local-first, lifecycle-aware software engineering CLI that
orchestrates a deterministic 12-stage SDLC pipeline. It enforces quality gates,
manages artifact dependencies, learns from past mistakes, and can spawn AI agents
through a provider-agnostic adapter interface — all from a single `forge`
command.

---

## Status: Phase 08 In Progress

The project is in active development. Phase 01 through Phase 07 are complete.
Phase 08 (Backtrack, Rework, Security, ACP) is the current focus — backtrack and
security backends are complete; gates are partially built; ACP integration is
CLI-scaffolded awaiting backend implementation.

---

## What's Working Today

### CLI Commands

| Command | Phase | Description |
|---------|-------|-------------|
| `forge init` | 01 | Initialize a Forge project (minimal/standard/expert) |
| `forge status` | 01 | Show project name, profile, stage, stale artifacts |
| `forge config show` | 01 | Print validated config as YAML |
| `forge config validate` | 01 | Validate a config file or project config |
| `forge explain <topic>` | 01 | Explain a Forge OS concept |
| `forge stage list` | 02 | List all pipeline stages |
| `forge stage start <id>` | 02 | Start a stage |
| `forge stage complete <id>` | 02 | Mark a stage complete |
| `forge stage advance` | 02 | Complete active stage, start next |
| `forge stage override <id>` | 02 | Force a stage with an audit reason |
| `forge events list` | 03 | List lifecycle events |
| `forge events tail -n N` | 03 | Tail the last N events |
| `forge gate list` | 04 | List configured gates |
| `forge gate check <stage>` | 04 | Evaluate gates for a stage |
| `forge gate report` | 04 | Render a readable gate report |
| `forge adapter list` | 05 | Show adapter priority and status |
| `forge agent list` | 05 | List built-in and project personas |
| `forge agent contracts` | 05 | List output contracts |
| `forge agent run` | 05 | Run the stage agent |
| `forge lesson list` | 06 | List project lessons |
| `forge lesson add <text>` | 06 | Add a manual lesson |
| `forge lesson approve <id>` | 06 | Approve a pending lesson |
| `forge lesson deprecate <id>` | 06 | Deprecate a lesson |
| `forge reflection list` | 06 | List stored reflections |
| `forge reflection show <id>` | 06 | Show one reflection as YAML |
| `forge artifact list` | 07 | List registered artifacts |
| `forge artifact register <path>` | 07 | Register an artifact |
| `forge artifact refresh` | 07 | Refresh artifact hashes |
| `forge context select <stage>` | 07 | Deterministic context pruning |
| `forge backtrack list` | 08 | List backtrack tickets |
| `forge backtrack plan <id>` | 08 | Show rework plan for a ticket |
| `forge backtrack approve <id>` | 08 | Approve a ticket for execution |
| `forge backtrack run <id>` | 08 | Execute rework for a ticket |
| `forge security audit` | 08 | View security audit log |
| `forge acp discover` | 08 | Discover ACP agents from registry ⚠️ CLI-scaffolded |
| `forge acp list` | 08 | List locally installed ACP agents ⚠️ CLI-scaffolded |
| `forge acp install <id>` | 08 | Install an ACP agent ⚠️ CLI-scaffolded |
| `forge acp sessions` | 08 | List active ACP sessions ⚠️ CLI-scaffolded |
| `forge acp close-session <id>` | 08 | Close an ACP session ⚠️ CLI-scaffolded |
| `forge health check` | 09 | Run subsystem health check |

### Completed Phases

- **Phase 01** — CLI scaffold: init, status, config, explain
- **Phase 02** — State machine: 12-stage pipeline, atomic writes, event logging
- **Phase 03** — Lifecycle events: normalized JSONL, in-process event bus
- **Phase 04** — Gates: file/pattern gates, severity, reports, advancement enforcement
- **Phase 05** — Adapters & agents: KernelAdapter interface, DummyAdapter, 12 stage personas
- **Phase 06** — Memory: lesson store, reflections, approval workflow
- **Phase 07** — ADG & context: artifact registry, stale propagation, deterministic pruning

### In Progress

- **Phase 08** — Backtrack, Security, ACP
  - Backtrack ticket schema, store, and CLI (list/plan/approve/run) ✅
  - Rework planner and approval flow ✅
  - ADG cascade generation — pending
  - Stale flag cleanup after revalidation — pending
  - Security profiles and enforcement (path, command, timeout) ✅
  - Security audit log (`.forge/security-audit.jsonl`) ✅
  - ACP CLI commands scaffolded (non-functional until backend) ⚠️
  - ACPClient (JSON-RPC over stdio) — pending
  - ACPRegistryAdapter (registry fetch + install) — pending
  - IKernelAdapter ACP enhancements (spawn, list, session mgmt) — pending
  - ExternalCommand and MetricThreshold gates — pending
  - Phase 08 tests — not yet written

### Upcoming

- **Phase 08.5** — Async adapter migration, CocoIndex evaluation, Event Store groundwork
- **Phase 09** — Health checks, global memory, skill mining, ACP agent health
- **Phase 10** — Daemon, dreamer, lazy context builder
- **Phase 11** — Channel adapters, OpenClaw, extension/plugin system

---

## Architecture

```
forge_os/
├── adapters/          # KernelAdapter implementations (DummyAdapter, registry)
├── agents/            # Personas, output contracts, executor
├── cli/               # Typer CLI
│   ├── main.py        # Root app (895 lines)
│   ├── commands/      # Phase 08+ command modules
│   │   ├── backtrack.py  # forge backtrack CLI
│   │   ├── security.py   # forge security CLI
│   │   ├── health.py     # forge health CLI (Phase 09 scaffold)
│   │   └── acp.py        # forge acp CLI (scaffolded, backend pending)
│   └── _shared.py     # Shared console and project resolution
├── config/            # Config loading and validation
├── context/           # Artifact registry, ADG, context pruning
├── core/              # StateManager, atomic writes, transitions
├── events/            # Event bus, event log
├── gates/             # Gate coordinator, evaluator, loader (ext/missing)
├── hooks/             # Hook registry
├── kernel/            # ⏳ Planned: ACPClient, ACPRegistryAdapter
├── memory/            # Lessons, reflections
├── project/           # Detection, scaffold, profiles,
│                      # backtrack_registry, rework_planner,
│                      # security_enforcer, security_audit
├── schemas/           # Pydantic models (state, config, backtrack, security)
└── use_cases/         # Business logic (backtrack, security, gates)
```

Phase 08+ commands live in `cli/commands/<domain>.py` and delegate to the
`use_cases/` layer. `main.py` handles only parsing, output formatting, and
error translation. See `plan/PHASE-08-backtrack-security.md` for full scope.

⚠️ ACP CLI commands are scaffolded but non-functional — backend modules
(`kernel/acp_client.py`, `kernel/acp_registry_adapter.py`,
`use_cases/acp.py`) are not yet implemented.

---

## Quick Start

```bash
# Install
pip install .

# Initialize a project
forge init --path ./my-project --profile minimal

cd ./my-project

# Walk through the pipeline
forge stage list
forge stage start spec
forge stage complete spec
forge stage advance

# Check gates
forge gate check build
forge gate report

# Run an agent
forge agent run

# View health
forge health check
```

---

## Roadmap

See `ROADMAP.md` for detailed release milestones.

| Release | Target | Outcome |
|---------|--------|---------|
| 0.1 | Phases 01–02, 04 partial | Init, status, stages, basic gates |
| 0.2 | Phases 02–05 | Full pipeline, events, gates, agents |
| 0.3 | Phase 05 complete | Provider-agnostic agent execution |
| 0.4 | Phases 06–07 | Memory, ADG, context pruning |
| **0.5** | **Phase 08** | **Backtrack, security, ACP — current** |
| 0.6 | Phase 08.5 | Async migration, CocoIndex, Event Store |
| 1.0 | Phase 09 | Health checks, global memory, skills |
| 1.5 | Phase 10 | Daemon, dreamer, lazy context |
| 2.0 | Phase 11 | Channels, OpenClaw, extensions |

---

## Contributing

1. Read `plan/PHASE-XX-*.md` for the phase you want to work on.
2. Read `BUILD_SPEC.md` for package layout and tooling conventions.
3. All new CLI commands must be added to `src/forge_os/cli/commands/<domain>.py`
   and registered with `app.add_typer()` in `main.py`.
4. Business logic belongs in `use_cases/` — CLI code is thin.
5. Run `.venv/bin/python -m pytest` before committing (67 tests pass as of Phase 08
   partial; target is 120+).
6. See `plan/PHASE-08-backtrack-security.md` → "Notes for the Next Implementer"
   for Phase 08-specific guidance.