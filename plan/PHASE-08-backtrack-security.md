# Phase 08 — Backtrack, Rework, and Security Baseline

## Status

not-started

## Objective

Add scoped rework planning and enforce a basic security model around tools, paths, commands, and state files.

## Scope

Included:

- Backtrack ticket schema
- Rework cascade planning from ADG
- Manual approval flow
- Diff-mode stage rerun flag
- Tool/security profile schema
- Path/command restrictions
- Security audit log
- ExternalCommand and MetricThreshold gates, if not already implemented

Excluded:

- Docker/OS-level deep sandbox
- Fully automated rework without approval
- Channel security

## Dependencies

- Phase 07 complete

## Deliverables

1. Backtrack ticket system.
2. Rework plan generator.
3. User approval commands.
4. Security profile enforcement baseline.
5. Protected state files.
6. External command gate support with timeout.
7. Security audit log.

## Tasks

| ID | Task |
|---|---|
| P08.01 | Define backtrack ticket schema |
| P08.02 | Add `forge backtrack list` |
| P08.03 | Add `forge backtrack plan <id>` |
| P08.04 | Generate affected stages from ADG |
| P08.05 | Add `forge backtrack approve <id>` |
| P08.06 | Add `forge backtrack run <id>` in diff mode |
| P08.07 | Clear stale flags after revalidation |
| P08.08 | Define tool/security profile schema |
| P08.09 | Enforce path restrictions for tools |
| P08.10 | Prevent agents from directly writing state files |
| P08.11 | Add command allowlist and timeout runner |
| P08.12 | Implement `ExternalCommand` gate |
| P08.13 | Implement `MetricThreshold` gate |
| P08.14 | Write `.forge/security-audit.jsonl` |
| P08.15 | Add tests for rework/security/gates |

## Acceptance Criteria

- Rework cascades require human approval.
- Only affected stages/artifacts are targeted.
- Agents cannot directly modify core state files.
- External commands cannot hang indefinitely.
- Tool and security actions are audited.
- Metric gates can pass/fail based on parsed output.

## Exit Checklist

- [ ] Backtrack tickets work
- [ ] Rework planning works
- [ ] Approval flow works
- [ ] Security profiles enforced
- [ ] ExternalCommand gates work
- [ ] MetricThreshold gates work
- [ ] Tests pass
- [ ] `CURRENT_PHASE.md` updated to Phase 09

## Suggested Next Prompt

`Implement Phase 08 only: backtrack tickets, rework cascade planning, security profiles, external command gates, metric gates, and audit logging.`
