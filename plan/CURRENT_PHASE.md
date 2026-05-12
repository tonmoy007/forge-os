# Current Forge OS Phase

## Current Phase

- Phase: 08
- File: `plan/PHASE-08-backtrack-security.md`
- Status: in-progress

## Current Objective

Add scoped rework planning, enforce a basic security model around tools, paths, commands, and state files, and integrate ACP (Agent Client Protocol) registry discovery with IKernelAdapter enhancements to enable Forge OS to spawn and manage ACP-compatible coding agents.

## Last Completed Phase

- Phase: 07
- File: `plan/PHASE-07-adg-context.md`
- Status: complete

## Phase 08 Scope Expansion

Phase 08 has been expanded to include ACP (Agent Client Protocol) integration based on the ACP Registry RFD and IKernelAdapter enhancements research. The ACP integration provides:

- **ACP Registry Discovery** — Fetch and parse the official ACP Registry (`https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`) to discover compatible coding agents
- **ACPClient** — JSON-RPC over stdio communication with ACP-compatible agents (Gemini CLI, Copilot CLI, Codex, Claude Code via ACPx, etc.)
- **Session Management** — session/list, session/resume, session/close (all stabilized April 2026)
- **Agent Lifecycle** — discover, install (binary/npx/uvx), spawn, manage ACP agents from within Forge OS
- **IKernelAdapter Enhancements** — spawn_acp_agent, list_acp_agents, get_acp_registry_adapter, is_acp_available
- **Adapter Fallback Chain** — OpenClawAdapter → OpenCodeAdapter → LocalLLMAdapter → HumanAdapter

### Why ACP in Phase 08?

1. `IKernelAdapter` is Phase 05 infrastructure — ACP is a natural extension of it
2. External command gates (P08.12) benefit directly from ACP agent spawning
3. Backtrack diff-mode rerun (P08.06) can leverage ACP session resume
4. Phase 11 (`forge plug`, OpenClawAdapter) already has "Implement offline fallback to another adapter" — ACP makes that fallback meaningful
5. Phase 09 (Health) will use ACP session health checks for agent restart logic

## Resolved Decisions

1. Runtime: Python 3.11+.
2. Package import name: `forge_os`.
3. Preferred CLI command: `forge`.
4. Development package manager preference: `uv`, while preserving standard `pip` compatibility.
5. Distribution: local Python package first, `pipx` when ready, standalone binary later.
6. Adapter priority:
   1. `DummyAdapter`
   2. `ClaudeCodeAdapter`
   3. `CodexAdapter`
   4. `OpenClawAdapter`
   5. `OpenCodeAdapter`
   6. `LocalLLMAdapter`
   7. `HumanAdapter`
7. OpenClawAdapter architecture: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
8. Core state ownership: Forge OS core is the sole writer of canonical state.
9. Open formats: YAML, JSON, JSON Lines, Markdown, and GraphML.
10. Security baseline: least privilege, human approval for high-risk/destructive actions, explicit timeouts for executable checks.
11. ACP Protocol: JSON-RPC 2.0 over newline-delimited JSON on stdio.
12. ACP Registry: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
13. ACP session features (list, resume, close) are stabilized as of April 2026.
14. ACP agents must be registered in the official ACP Registry at `github.com/agentclientprotocol/registry`.
15. ACP integration is additive — existing LiteLLMAdapter behavior is preserved.
16. ACP agent installation supports: binary archives, npx packages, and uvx packages per manifest.
17. ACP agents spawned by Forge OS must respect SecurityEnforcer policies.
18. Phase 01 CLI scaffold is complete with `forge init`, `forge status`, `forge config show`, `forge config validate`, and `forge explain`.
19. Phase 02 state machine is complete with `forge stage list/start/complete/advance/override`, atomic writes, transition validation, state markdown sync, and transition event logging.
20. Phase 03 events/hooks are complete with normalized lifecycle events, in-process event bus, hook registry, hook timeout/failure isolation, and `forge events list/tail`.
21. Phase 04 gates MVP is complete with file/pattern gates, severity handling, gate reports, `forge gate list/check/report`, gate events, persisted latest results, and stage advancement enforcement.
22. Phase 05 adapters/agents are complete with KernelAdapter interface, adapter registry/config placeholders, DummyAdapter, 12 stage personas, 4 cross-stage personas, output contracts, agent execution logs, `forge adapter list`, `forge agent list/contracts/run`, and optional `forge stage start --spawn-agent`.
23. Phase 06 memory/lessons are complete with YAML lesson store, reflection files, lesson add/list/approve/deprecate CLI, reflection list/show CLI, stage-completion reflection capture, pending lesson extraction queue, and approved high-confidence lesson injection into agent context.
24. Phase 07 ADG/context is complete with artifact registry, JSON ADG persistence, stale downstream propagation, deterministic spread-activation context pruning, context selection audit logs, artifact/context CLI commands, stale artifact display in `forge status`, and pruned context integration for agent spawns.
25. **Phase 08 CLI refactoring complete** — all Phase 08+ commands moved to `src/forge_os/cli/commands/` sub-modules (`backtrack.py`, `security.py`, `health.py`, `acp.py`). `main.py` slimmed from 1240→895 lines. Separation of concerns enforced for all future commands.

## Blocking Questions

None currently.

## Phase 08 Task Summary

### Backtrack & Rework
| ID | Task |
|---|---|
| P08.01 | Define backtrack ticket schema |
| P08.02 | Add `forge backtrack list` ✅ |
| P08.03 | Add `forge backtrack plan <id>` ✅ |
| P08.04 | Generate affected stages from ADG |
| P08.05 | Add `forge backtrack approve <id>` ✅ |
| P08.06 | Add `forge backtrack run <id>` in diff mode ✅ |
| P08.07 | Clear stale flags after revalidation |

### Security Profiles & Enforcement
| ID | Task |
|---|---|
| P08.08 | Define tool/security profile schema |
| P08.09 | Enforce path restrictions for tools |
| P08.10 | Prevent agents from directly writing state files |
| P08.11 | Add command allowlist and timeout runner |
| P08.14 | Write `.forge/security-audit.jsonl` ✅ |

### Gates
| ID | Task |
|---|---|
| P08.12 | Implement `ExternalCommand` gate |
| P08.13 | Implement `MetricThreshold` gate |
| P08.15 | Add tests for rework/security/gates |

### ACP Registry & Agent Discovery
| ID | Task |
|---|---|
| P08.16 | Define `ACPRegistryAdapter` interface |
| P08.17 | Implement `ACPRegistryAdapter` |
| P08.18 | Implement `ACPClient` (JSON-RPC over stdio) ✅ |
| P08.19 | Add session management methods ✅ |
| P08.20 | Add `session_config_options` |
| P08.21 | Add session info update handling |
| P08.22 | Implement agent installation (binary/npx/uvx) ✅ |
| P08.23 | Add `forge acp discover` ✅ |
| P08.24 | Add `forge acp install <agent-id>` ✅ |
| P08.25 | Add `forge acp list` ✅ |
| P08.26 | Add `forge acp sessions` ✅ |
| P08.27 | Add `forge acp close-session <id>` ✅ |

### IKernelAdapter ACP Enhancements
| ID | Task |
|---|---|
| P08.28 | Add `spawn_acp_agent` to `IKernelAdapter` |
| P08.29 | Add `list_acp_agents` to `IKernelAdapter` |
| P08.30 | Add `get_acp_registry_adapter` to `IKernelAdapter` |
| P08.31 | Add `is_acp_available` to `IKernelAdapter` |
| P08.32 | Enhance `LiteLLMAdapter` with ACP support |

### ACP Adapter Fallback Chain
| ID | Task |
|---|---|
| P08.33 | Implement adapter priority chain |
| P08.34 | Wire ACP agents into backtrack rerun |
| P08.35 | ACP integration tests |

## Notes For The Next Implementer

Read:

1. `BUILD_SPEC.md`
2. `plan/ORCHESTRATOR.md`
3. `plan/PHASE-08-backtrack-security.md` (expanded with ACP tasks)
4. `plan/PHASE-07-adg-context.md`
5. `plan/PHASE-06-memory-lessons.md`
6. `plan/PHASE-05-adapters-agents.md`
7. `plan/PHASE-11-channels-openclaw-extensions.md` (OpenClaw integration builds on ACP)
8. `plan/KERNEL_ADAPTER_INTERFACE.md`
9. `plan/ADAPTER_ROADMAP.md`
10. `ARCHITECTURE.md`
11. `SCHEMAS.md`
12. Existing Phase 01-07 code under `src/forge_os/`
13. Existing tests under `tests/`
14. **`src/forge_os/cli/commands/` — new command modules for Phase 08+**

Phase 08 should implement backtrack/rework, security baseline, and ACP integration only. Do not implement daemon, channels, OpenClaw full integration, or plugins early.

### ACP-Specific Implementation Notes

- ACP Registry URL: `https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json`
- ACP uses JSON-RPC 2.0 over newline-delimited JSON on stdio
- All session methods (list, resume, close) are stabilized as of April 2026
- ACP agents must be registered in the official registry at `github.com/agentclientprotocol/registry`
- Fallback chain: `OpenClawAdapter → OpenCodeAdapter → LocalLLMAdapter → HumanAdapter`
- ACP integration is additive; existing LiteLLMAdapter behavior is preserved
- ACP agents must respect SecurityEnforcer policies

### CLI Refactoring Rule (Enforced)

All new Phase 08+ commands MUST live in their own file under `src/forge_os/cli/commands/<domain>.py`.
Each file exposes a Typer sub-app (e.g. `backtrack_app`, `acp_app`).
Register with `app.add_typer()` in `main.py`.
Business logic belongs in `use_cases/`, not in CLI command files.

### Directory Structure Additions

```
src/forge_os/
├── cli/
│   ├── main.py              # Slimmed root app (895 lines)
│   └── commands/            # Phase 08+ command modules
│       ├── __init__.py
│       ├── _shared.py        # Shared console, helpers
│       ├── backtrack.py     # backtrack_app
│       ├── security.py      # security_app
│       ├── health.py        # health_app
│       └── acp.py          # acp_app
├── kernel/
│   ├── acp_client.py           # ACPClient for JSON-RPC/stdio
│   ├── acp_registry_adapter.py # ACPRegistryAdapter for agent discovery
│   └── adapter.py              # Enhanced IKernelAdapter with ACP methods
├── project/
│   ├── use_cases/
│   │   ├── backtrack_*.py      # Backtrack ticket use cases
│   │   └── security_*.py      # Security enforcement use cases
│   ├── backtrack/
│   │   └── ticket.py           # BacktrackTicket model and BacktrackStore
│   └── security/
│       ├── profile.py          # SecurityProfile model
│       ├── enforcer.py         # SecurityEnforcer
│       └── audit_log.py        # AuditLog for JSONL logging
└── gates/
    ├── external_command.py     # ExternalCommandGate
    └── metric_threshold.py     # MetricThresholdGate
```

Last validation commands:

- `.venv/bin/python -m pytest` — 67 passed.
- `.venv/bin/python -m ruff check src tests` — passed.
- `.venv/bin/python -m compileall src tests` — passed.

Expected test count after Phase 08: 120+ passed.