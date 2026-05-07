# Phase 11 — Channels, OpenClawAdapter, and Extensions

## Status

not-started

## Objective

Complete the v2 ecosystem layer: safe channel interaction, optional OpenClaw execution adapter, and community extension support.

## Scope

Included:

- Channel adapter interface
- Console/dummy channel adapter
- Status query via channel
- Feedback intake via channel
- Release broadcast
- OpenClawAdapter interface and implementation, if API docs are available
- Adapter fallback
- Extension manifest
- `forge plug` commands
- Extension permission validation

Excluded:

- Making OpenClaw mandatory
- Letting channels execute unsafe tools by default
- Unsandboxed extensions

## Dependencies

- Phase 10 complete
- `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md` exists
- Concrete OpenClaw HTTP/WebSocket endpoint details for full implementation

## Deliverables

1. Channel adapter interface.
2. Safe channel status/feedback/release workflows.
3. OpenClawAdapter following `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md`, or documented endpoint-level placeholders if concrete API details are unavailable.
4. Extension manifest schema.
5. Local extension discovery/install/remove.
6. Extension permission validation.

## Tasks

| ID | Task |
|---|---|
| P11.01 | Define channel adapter interface |
| P11.02 | Implement console/dummy channel adapter |
| P11.03 | Normalize incoming channel messages |
| P11.04 | Add read-only status query |
| P11.05 | Add feedback intake to Stage 10 |
| P11.06 | Add release broadcast |
| P11.07 | Add rate limiting and deduplication |
| P11.08 | Confirm concrete OpenClaw HTTP/WebSocket endpoints, webhook payloads, and auth details |
| P11.09 | Define OpenClaw config schema |
| P11.10 | Translate Forge agent persona to OpenClaw session config |
| P11.11 | Map Forge tool profiles to OpenClaw tool policy |
| P11.12 | Bridge OpenClaw webhooks to Forge lifecycle events |
| P11.13 | Sync valuable OpenClaw outputs back to `.forge/` without overwriting source truth |
| P11.14 | Implement offline fallback to another adapter |
| P11.15 | Define extension manifest schema |
| P11.16 | Implement `forge plug list/install/remove` for local extensions |
| P11.17 | Validate extension permissions |
| P11.18 | Detect extension conflicts |
| P11.19 | Add channel/OpenClaw/extension tests with mocks |

## Acceptance Criteria

- Channel messages cannot modify project files unless explicitly allowed.
- Status queries are read-only and fast.
- Feedback becomes structured pipeline input.
- OpenClaw is optional and failure does not corrupt Forge state.
- OpenClawAdapter follows Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
- OpenClaw memory cannot overwrite Forge source-of-truth files.
- OpenClaw forwards gate requests back to Forge Core instead of deciding gates internally.
- Extensions declare permissions and cannot bypass the state machine.

## Exit Checklist

- [ ] Channel interface works
- [ ] Channel status/feedback/release workflows work
- [ ] OpenClawAdapter implemented or blocked only on concrete endpoint/auth/webhook details
- [ ] Extension manifest works
- [ ] Local plug commands work
- [ ] Permission validation works
- [ ] Tests pass
- [ ] v2 definition of done reviewed

## Suggested Next Prompt

`Implement Phase 11 only: channel adapters, optional OpenClawAdapter, and extension/plugin system. If OpenClaw API docs are missing, create the interface and mock tests only.`
