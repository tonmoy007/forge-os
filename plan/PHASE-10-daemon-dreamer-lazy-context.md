# Phase 10 — Background Daemon, Dreamer, and Lazy Context

## Status

not-started

## Objective

Add optional always-on behavior: background daemon, Observer scheduling, Dreamer daily/weekly maintenance, lesson decay, lazy context loading, and continuous ACP agent health monitoring via the session management foundation from Phase 08.

## Scope

Included:

- Optional daemon process
- Daemon start/stop/status commands
- Scheduled tasks
- Dreamer daily digest
- Weekly re-ingestion/tension detection
- Lesson decay
- Lazy skill menu
- Lazy lesson index
- Token budget guard
- ACP agent health monitoring as a daemon task
- Agent session monitoring and auto-recovery

Excluded:

- Channel adapters
- OpenClaw full integration
- Remote server/team deployment

## Dependencies

- Phase 09 complete (includes ACP agent health checks)
- Phase 08 complete (ACPClient, ACPRegistryAdapter, session management)

## Deliverables

1. `forge daemon start`
2. `forge daemon stop`
3. `forge daemon status`
4. Dreamer daily digest
5. Lesson decay
6. Observer monitoring config foundation
7. Lazy Context Builder
8. ACP agent health monitoring as a daemon task
9. Scheduled ACP session cleanup

## Tasks

### Daemon Core

| ID | Task | Notes |
|---|---|---|
| P10.01 | Implement daemon process model | Optional background process, survives CLI exit |
| P10.02 | Implement daemon state persistence | Persist daemon state to `~/.forge/daemon/state.json` |
| P10.03 | Add daemon CLI commands | `forge daemon start/stop/status/logs` |
| P10.04 | Add scheduled task runner | Interval-based task scheduling within daemon |

### Dreamer

| ID | Task | Notes |
|---|---|---|
| P10.05 | Implement Dreamer daily digest | Write to `pipeline/log/daily-YYYY-MM-DD.md` |
| P10.06 | Implement weekly reflection re-ingestion | Re-process past reflections for pattern detection |
| P10.07 | Detect lesson tensions for human review | Conflicting lessons flagged for approval |
| P10.08 | Apply lesson confidence decay | Confidence scores decrease over time without reinforcement |
| P10.09 | Mark dormant lessons | Lessons not used in 30+ days flagged as dormant |

### Observer & Health

| ID | Task | Notes | Dependencies |
|---|---|---|---|
| P10.10 | Add Observer monitoring config and polling stub | Periodic health checks via daemon | P10.04 |
| P10.11 | Add alert output to status | Daemon alerts surface in `forge status` | P10.10 |
| P10.12 | Add ACP agent health as daemon task | Scheduled ACP session monitoring | P10.04, Phase 09 ACP health |
| P10.13 | Auto-recover failed ACP agents | Restart agents detected unhealthy | P10.12, Phase 09 P09.20 |
| P10.14 | Track daemon-level agent uptime | Persist uptime metrics to `~/.forge/daemon/metrics.json` | P10.12 |

### Lazy Context

| ID | Task | Notes |
|---|---|---|
| P10.15 | Implement skill menu injection | Lazy-load available skills on demand |
| P10.16 | Implement on-demand skill expansion | Skills loaded into context only when referenced |
| P10.17 | Implement low-confidence lesson index | Fast index of lessons below approval threshold |
| P10.18 | Enforce context budget during lazy loads | Reject context additions that exceed budget |
| P10.19 | Measure context size reduction | Report before/after lazy context size |

### Testing

| ID | Task |
|---|---|
| P10.20 | Add daemon/dreamer/lazy context tests |
| P10.21 | Add daemon ACP monitoring tests |

## ACP Agent Health as Daemon Task

The daemon runs ACP agent health monitoring as a scheduled background task:

```
forge daemon start
    │
    ▼
Daemon initializes
    │
    ├──► Load Phase 08 ACPClient
    ├──► Load Phase 09 ACP health checks
    └──► Start scheduled task runner
            │
            ├──► Every 60s: ACP registry accessibility check
            ├──► Every 5min: session/list → detect stale sessions
            ├──► Every 5min: session/close on stale sessions
            ├──► On detection: Agent restart via ACPClient
            └──► On recovery: Log to .forge/security-audit.jsonl
```

### Daemon Task Schedule

| Task | Interval | Phase 09 Equivalent |
|---|---|---|
| Registry health | 60s | P09.18 |
| Session list/cleanup | 5min | P09.19 |
| Agent restart | On failure | P09.20 |
| Health metrics persist | 5min | P09.21 |

### Daemon ACP State

```json
{
  "daemon_id": "uuid",
  "started_at": "ISO8601",
  "ACP": {
    "monitoring_enabled": true,
    "last_check": "ISO8601",
    "active_sessions": ["session-id-1", "session-id-2"],
    "stale_sessions_cleaned": 0,
    "agents_restarted": 0,
    "agent_uptime": {
      "github-copilot": { "uptime_seconds": 3600, "restarts": 0 },
      "gemini-cli": { "uptime_seconds": 7200, "restarts": 1 }
    }
  }
}
```

## Architecture: Daemon Layer

```
┌──────────────────────────────────────────────────────────────┐
│                     Forge OS Daemon Layer                      │
├──────────────────────────────────────────────────────────────┤
│  forge daemon start                                          │
│  ├── Daemon state persistence                                │
│  ├── Scheduled task runner                                  │
│  └── Signal handling (SIGTERM, SIGHUP)                      │
├──────────────────────────────────────────────────────────────┤
│  Scheduled Tasks                                             │
│  ├── ACP Health Monitor (Phase 09 health wired here)        │
│  │   ├── Registry accessibility                             │
│  │   ├── Session list/cleanup                              │
│  │   └── Agent restart                                     │
│  ├── Dreamer Daily Digest                                   │
│  ├── Lesson Decay                                          │
│  └── Observer Polling                                       │
├──────────────────────────────────────────────────────────────┤
│  Dreamer                                                     │
│  ├── Daily digest (pipeline/log/daily-*.md)               │
│  ├── Weekly re-ingestion                                    │
│  └── Lesson tension detection                               │
├──────────────────────────────────────────────────────────────┤
│  Lazy Context Builder                                       │
│  ├── Skill menu injection (lazy)                           │
│  ├── Low-confidence lesson index                           │
│  └── Context budget enforcement                            │
└──────────────────────────────────────────────────────────────┘
```

## CLI Commands Added

| Command | Description |
|---|---|
| `forge daemon start` | Start the background daemon |
| `forge daemon stop` | Stop the daemon gracefully |
| `forge daemon status` | Show daemon health and active tasks |
| `forge daemon logs` | Stream daemon log output |
| `forge daemon restart` | Stop and restart the daemon |
| `forge dreamer digest` | Force a Dreamer daily digest |
| `forge dreamer scan` | Run lesson tension detection |
| `forge context budget` | Show current context budget usage |
| `forge context lazy-stats` | Show lazy context reduction metrics |

## Acceptance Criteria

- Daemon is optional; core CLI works without it
- Daemon survives restart using persisted state
- Dreamer creates daily digest if activity occurred
- Dreamer proposes destructive changes but never applies them without approval
- Dormant lessons are not injected into context
- Lazy context reduces eager prompt size and respects budget
- ACP agent health monitoring runs as a daemon scheduled task
- Stale ACP sessions are automatically cleaned up by the daemon
- Failed ACP agents are automatically restarted by the daemon
- ACP health failures in daemon mode do not crash the daemon

## Exit Checklist

- [ ] Daemon commands work (`forge daemon start/stop/status/logs`)
- [ ] Daemon persists state across restarts
- [ ] Dreamer digest works
- [ ] Lesson decay works
- [ ] Observer stub works
- [ ] Lazy context works
- [ ] ACP agent health monitoring runs as daemon task
- [ ] Auto-recovery of failed ACP agents works
- [ ] Daemon ACP metrics persisted
- [ ] Tests pass
- [ ] `CURRENT_PHASE.md` updated to Phase 11

## Notes For The Implementer

Key references:
1. `plan/PHASE-08-backtrack-security.md` — ACP foundation (ACPClient, ACPRegistryAdapter, session management)
2. `plan/PHASE-09-health-global-skills.md` — ACP health checks (P09.18–P09.23)
3. `plan/PHASE-06-memory-lessons.md` — Existing lesson store implementation
4. `plan/PHASE-07-adg-context.md` — Context pruning and budget management
5. `src/forge_os/daemon/` — Daemon module (create if needed)
6. `src/forge_os/kernel/acp_client.py` — ACP session management
7. `src/forge_os/dreamer/` — Dreamer module (create if needed)

ACP-specific notes:
- ACP monitoring runs as a scheduled daemon task, not a one-shot health check
- Session cleanup (session/close) runs every 5 minutes via scheduled task runner
- Agent restart respects `SecurityEnforcer` policies even in daemon mode
- Daemon ACP state is persisted to `~/.forge/daemon/metrics.json` for uptime tracking
- ACP failures are logged but do not crash the daemon
- Use Phase 09's `forge health acp` as the implementation base for the daemon task

Phase 10 does NOT implement:
- Channel adapters (Phase 11)
- OpenClaw full integration (Phase 11)
- Remote/server deployment

## Suggested Next Prompt

`Implement Phase 10: optional daemon, Dreamer daily/weekly maintenance, lesson decay, Observer stub, lazy context builder, and ACP agent health monitoring as a daemon scheduled task using Phase 08 session management and Phase 09 health checks.`
