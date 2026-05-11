# Forge OS Definition of Done

## Phase Completion

A phase is complete when:

- All deliverables in the phase file exist.
- Acceptance criteria are satisfied.
- Tests/checks relevant to the phase have been run.
- Deferred work is explicitly recorded.
- `plan/CURRENT_PHASE.md` is updated.
- No future-phase implementation has been added accidentally.

## v1 Completion

Forge OS v1 is done when:

- Local installation works.
- `forge init` creates a valid project.
- Minimal and standard profiles work.
- Stage transitions are deterministic.
- Gates block/warn correctly.
- `DummyAdapter` works deterministically for tests.
- `ClaudeCodeAdapter` is available or clearly documented as deferred after v1.
- Adapter roadmap is implemented in the selected order or deviations are recorded in ADRs.
- Agent personas and output contracts exist.
- Lessons can be extracted, approved, deprecated, and reused.
- ADG marks stale artifacts.
- Context pruning is deterministic.
- Backtrack tickets can be generated and approved.
- External command gates have timeout and safety restrictions.
- Health check detects broken hooks/gates/knowledge issues.
- State writes are atomic.
- Documentation explains usage and extension basics.

## v2 Completion

Forge OS v2 is done when:

- v1 is stable.
- Optional daemon works.
- Dreamer produces daily digests and applies non-destructive maintenance.
- Lesson decay works.
- Lazy context builder reduces eager context size.
- Channel adapters support safe status, feedback, and release broadcast.
- OpenClawAdapter works or is formally deferred due to missing external API docs.
- Extensions can be installed/removed safely.
- Extension permissions are validated.
- Security audit trail covers tool use and permission escalation.
