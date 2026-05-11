# Phase 09 — Health, Global Memory, Skill Mining, and ACP Agent Health

## Status

not-started

## Objective

Prepare Forge OS for v1 stability by adding health checks, global cross-project memory, profile adaptation, approved skill mining, and ACP agent health monitoring using session management from Phase 08.

## Scope

Included:

- `forge health check`
- Hook tests
- Gate simulations
- Knowledge integrity checks
- Token budget report
- Global memory directory
- Global lesson promotion
- Project profiles memory
- Pattern tracking
- Skill proposal and approval
- ACP agent health checks using Phase 08 session management
- Agent restart/recovery logic
- Session health monitoring

Excluded:

- Scheduled daemon health checks
- Dreamer cycle
- Extension registry
- OpenClaw full integration (Phase 11)

## Dependencies

- Phase 08 complete (ACP foundation: ACPClient, ACPRegistryAdapter, session management)

## Deliverables

1. Health check command.
2. Golden good/bad artifacts for gate simulations.
3. Knowledge integrity scanner.
4. Global memory under `~/.forge/`.
5. Global lesson promotion with approval.
6. Pattern tracker.
7. Skill proposal/approval/install commands.
8. ACP agent health checks using session/list and session/config/options.
9. Agent restart and recovery logic.

## Tasks

### Health Checks

| ID | Task | Notes |
|---|---|---|
| P09.01 | Implement `forge health check` | Core health command covering all subsystems |
| P09.02 | Add hook unit test harness | Validate hook registration and execution |
| P09.03 | Add gate simulation fixtures | Known-good and known-bad gate scenarios |
| P09.04 | Run known-good/known-bad gate simulations | Ensure gates detect failures correctly |
| P09.05 | Scan lessons for missing artifact references | Knowledge integrity for Phase 06 lessons |
| P09.06 | Scan lessons for conflicts/duplicates | Basic deterministic rules |
| P09.07 | Report token budget overages | Context length and token budget monitoring |

### Global Memory

| ID | Task | Notes |
|---|---|---|
| P09.08 | Create global Forge directory | `~/.forge/` for cross-project data |
| P09.09 | Implement global lesson store | YAML-based like Phase 06 but at global level |
| P09.10 | Track lesson usage by project | Count which projects use which lessons |
| P09.11 | Suggest promotion after 3 projects | Lesson is approved globally after N projects benefit |
| P09.12 | Add global promotion approval | Human approval before global lesson promotion |

### Pattern Tracking & Skill Mining

| ID | Task | Notes |
|---|---|---|
| P09.13 | Implement project profile memory | Per-project patterns (language, stack, tooling) |
| P09.14 | Track repeated action patterns | Detect recurring agent behaviors |
| P09.15 | Propose skills after threshold | Suggest skill installation after N repetitions |
| P09.16 | Add skill approval/install/list/run basics | Skill lifecycle management |
| P09.17 | Add health/global/skill tests | Unit and integration tests |

### ACP Agent Health

| ID | Task | Notes | Dependencies |
|---|---|---|---|
| P09.18 | Implement `forge health acp` | Check ACP registry accessibility and agent health | Phase 08 ACP |
| P09.19 | Add session health checks | Use `session/list` to detect stale sessions | P09.18, Phase 08 ACPClient |
| P09.20 | Add agent restart logic | Detect failed agents, restart via ACPClient | P09.19, Phase 08 ACPClient |
| P09.21 | Track agent uptime and failures | Persist agent health metrics | P09.19 |
| P09.22 | Wire ACP health into `forge health check` | Include ACP agent status in main health report | P09.18, P09.01 |
| P09.23 | Add ACP health tests | Mock ACP registry, test health detection | P09.18, Phase 08 ACP tests |

## ACP Agent Health Integration

Phase 09 uses the ACP session management features stabilized in Phase 08 to monitor agent health:

```
forge health check
    │
    ├──► State machine health
    ├──► Gate health
    ├──► ADG health
    ├──► Memory health
    └──► ACP Agent Health
            │
            ├──► session/list (detect stale sessions)
            ├──► session/config/options (verify agent capabilities)
            ├──► Registry accessibility check
            └──► Agent restart if failed
```

### Health Metrics Tracked

| Metric | Source | Action on Failure |
|---|---|---|
| Registry accessibility | `ACPRegistryAdapter.fetch_registry_json()` | Log warning, continue with cached agents |
| Agent process health | `ACPClient` subprocess check | Flag agent as unhealthy |
| Stale sessions | `session/list` response | Close stale sessions via `session/close` |
| Session timeout | Session metadata | Restart agent if session exceeds threshold |
| Installation failures | Agent install log | Report missing distribution method |

### Agent Recovery Flow

```
Detection (P09.19)
    │
    ▼
Stale/failed session detected via session/list
    │
    ▼
Call session/close on stale session (P09.20)
    │
    ▼
Query session/config/options for agent capabilities
    │
    ▼
Restart agent via ACPClient (P09.20)
    │
    ▼
Resume session or start fresh
    │
    ▼
Log recovery to .forge/security-audit.jsonl
```

## Architecture: Health Layer

```
┌─────────────────────────────────────────────────────────────┐
│                   Forge OS Health Layer                      │
├─────────────────────────────────────────────────────────────┤
│  forge health check                                        │
│  ├── state_machine: transition count, last transition       │
│  ├── gates: pass rate, last run, failures                 │
│  ├── adg: artifact count, stale count, context size      │
│  ├── memory: lesson count, global lesson count           │
│  └── acp_agents:                                         │
│       ├── registry_accessible: bool                       │
│       ├── installed_agents: List[AgentHealth]             │
│       ├── active_sessions: List[SessionInfo]             │
│       ├── stale_sessions: List[SessionInfo]              │
│       └── recommendations: List[HealthRecommendation]   │
├─────────────────────────────────────────────────────────────┤
│  Session Health Monitor (P09.19)                          │
│  ├── session/list polling                                 │
│  ├── stale session detection                               │
│  └── session/close for cleanup                            │
├─────────────────────────────────────────────────────────────┤
│  Agent Recovery (P09.20)                                  │
│  ├── Failure detection                                     │
│  ├── ACPClient restart                                     │
│  └── session resume or new session                        │
└─────────────────────────────────────────────────────────────┘
```

## Acceptance Criteria

- Health check produces actionable reports covering all subsystems.
- Known-good fixtures pass and known-bad fixtures fail.
- Broken hooks/gates are detected without crashing.
- Global lessons require approval before promotion.
- Skills require approval before installation.
- Rejected skill proposals are not repeatedly suggested.
- ACP agent health is included in `forge health check`.
- Stale sessions are detected and cleaned up via `session/close`.
- Failed agents can be restarted via ACPClient.
- ACP health failures do not block other health checks.

## Exit Checklist

- [ ] Health check works (`forge health check`, `forge health acp`)
- [ ] Gate simulations work
- [ ] Knowledge scan works
- [ ] Global memory works (`~/.forge/`)
- [ ] Skill mining approval works
- [ ] ACP agent health checks work
- [ ] Session health monitoring (list/close) works
- [ ] Agent restart/recovery works
- [ ] Tests pass
- [ ] Local v1 definition of done reviewed
- [ ] `CURRENT_PHASE.md` updated to Phase 10

## CLI Commands Added

| Command | Description |
|---|---|
| `forge health check` | Full system health report |
| `forge health acp` | ACP agent and registry health |
| `forge health gates` | Gate pass/fail history |
| `forge skill list` | List available skills |
| `forge skill propose <name>` | Propose a new skill |
| `forge skill approve <name>` | Approve a skill for installation |
| `forge skill install <name>` | Install an approved skill |
| `forge global lesson list` | List global lessons |
| `forge global lesson promote <id>` | Promote a project lesson to global |

## Notes For The Implementer

Key references:
1. `plan/PHASE-08-backtrack-security.md` — ACP foundation (ACPClient, ACPRegistryAdapter, session management)
2. `plan/PHASE-06-memory-lessons.md` — Existing lesson store implementation
3. `plan/PHASE-07-adg-context.md` — ADG health metrics
4. `src/forge_os/health/` — Health check module (create if needed)
5. `src/forge_os/kernel/acp_client.py` — ACP session management
6. `src/forge_os/kernel/acp_registry_adapter.py` — Registry health

ACP-specific notes:
- All session methods are stabilized as of April 2026
- Use `session/list` to enumerate active sessions and detect staleness
- Use `session/close` to clean up stale sessions without tearing down the ACP process
- Use `session/config/options` to verify agent capabilities after restart
- ACP health failures are non-fatal — log and continue
- Agent restart should respect `SecurityEnforcer` policies

Phase 09 does NOT implement:
- Scheduled/periodic health checks (Phase 10 daemon)
- Dreamer self-improvement cycle (Phase 10)
- Extension registry (Phase 11)

## Suggested Next Prompt

`Implement Phase 09: health checks, gate simulations, global memory, project profiles, skill mining, and ACP agent health monitoring using Phase 08 session management (session/list, session/close, session/config/options) for session monitoring and agent recovery.`
