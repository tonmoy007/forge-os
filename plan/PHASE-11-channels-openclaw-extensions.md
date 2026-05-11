# Phase 11 — Channels, OpenClawAdapter, and Extensions

## Status

not-started

## Objective

Complete the v2 ecosystem layer: safe channel interaction, optional OpenClaw execution adapter building on the ACP foundation from Phase 08, and community extension support.

## Scope

Included:

- Channel adapter interface
- Console/dummy channel adapter
- Status query via channel
- Feedback intake via channel
- Release broadcast
- OpenClawAdapter interface and implementation, if API docs are available, building on the ACPClient and ACPRegistryAdapter from Phase 08
- Adapter fallback chain using ACP session management
- Extension manifest
- `forge plug` commands
- Extension permission validation

Excluded:

- Making OpenClaw mandatory
- Letting channels execute unsafe tools by default
- Unsandboxed extensions
- ACP Registry implementation (Phase 08)
- ACPClient implementation (Phase 08)
- IKernelAdapter ACP enhancements (Phase 08)

## Dependencies

- Phase 10 complete
- Phase 08 complete (ACP foundation: ACPClient, ACPRegistryAdapter, session management)
- `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md` exists
- `plan/PHASE-08-backtrack-security.md` for ACP integration details
- Concrete OpenClaw HTTP/WebSocket endpoint details for full implementation

## Deliverables

1. Channel adapter interface.
2. Safe channel status/feedback/release workflows.
3. OpenClawAdapter following `plan/OPENCLAW_ADAPTER_ARCHITECTURE.md`, or documented endpoint-level placeholders if concrete API details are unavailable, built on ACPClient.
4. Extension manifest schema.
5. Local extension discovery/install/remove.
6. Extension permission validation.

## Tasks

| ID | Task | Dependencies |
|---|---|---|
| P11.01 | Define channel adapter interface | Phase 10 |
| P11.02 | Implement console/dummy channel adapter | P11.01 |
| P11.03 | Normalize incoming channel messages | P11.02 |
| P11.04 | Add read-only status query | P11.01 |
| P11.05 | Add feedback intake to Stage 10 | P11.03 |
| P11.06 | Add release broadcast | P11.04 |
| P11.07 | Add rate limiting and deduplication | P11.03 |
| P11.08 | Confirm concrete OpenClaw HTTP/WebSocket endpoints, webhook payloads, and auth details | Phase 10 |
| P11.09 | Define OpenClaw config schema | P11.08 |
| P11.10 | Translate Forge agent persona to OpenClaw session config | Phase 08 ACPClient, P11.09 |
| P11.11 | Map Forge tool profiles to OpenClaw tool policy | P11.09 |
| P11.12 | Bridge OpenClaw webhooks to Forge lifecycle events | P11.08, Phase 03 events |
| P11.13 | Sync valuable OpenClaw outputs back to `.forge/` without overwriting source truth | Phase 07 ADG |
| P11.14 | Implement offline fallback to another adapter | Phase 08 ACP fallback chain |
| P11.15 | Define extension manifest schema | Phase 10 |
| P11.16 | Implement `forge plug list/install/remove` for local extensions | P11.15 |
| P11.17 | Validate extension permissions | P11.16, Phase 08 SecurityEnforcer |
| P11.18 | Detect extension conflicts | P11.17 |
| P11.19 | Add channel/OpenClaw/extension tests with mocks | All above |

## ACP Foundation from Phase 08

Phase 11 builds on these Phase 08 ACP components:

```
Phase 08 — ACP Foundation
├── ACPClient (JSON-RPC / stdio)
│   ├── session/list, session/resume, session/close
│   └── streaming session/update handling
├── ACPRegistryAdapter
│   └── Agent discovery and installation
└── IKernelAdapter enhancements
    ├── spawn_acp_agent()
    ├── list_acp_agents()
    └── is_acp_available()

            ▼

Phase 11 — OpenClawAdapter
├── Inherits ACPClient for HTTP/WebSocket communication
├── Maps OpenClaw endpoints to ACP session methods
├── Bridges OpenClaw webhooks → Forge LifecycleEvent
└── Uses ACP session management for OpenClaw sessions
```

Key Phase 08 ACP components reused in Phase 11:

| Component | Reused In | Purpose |
|---|---|---|
| `ACPClient` | `OpenClawAdapter` | Base communication with OpenClaw Gateway |
| `ACPRegistryAdapter` | `OpenClawAdapter` | Agent discovery for OpenClaw-compatible agents |
| Session management | `OpenClawAdapter` | OpenClaw session list/resume/close via ACP |
| `SecurityEnforcer` | Extension validation | Extensions must respect security profiles |
| `ForgeAgentPersona` | `OpenClawAdapter` | Map persona to OpenClaw session config |

## Acceptance Criteria

- Channel messages cannot modify project files unless explicitly allowed.
- Status queries are read-only and fast.
- Feedback becomes structured pipeline input.
- OpenClaw is optional and failure does not corrupt Forge state.
- OpenClawAdapter follows Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.
- OpenClaw memory cannot overwrite Forge source-of-truth files.
- OpenClaw forwards gate requests back to Forge Core instead of deciding gates internally.
- Extensions declare permissions and cannot bypass the state machine.
- ACP session features are reused for OpenClaw session management.

## Exit Checklist

- [ ] Channel interface works
- [ ] Channel status/feedback/release workflows work
- [ ] OpenClawAdapter implemented or blocked only on concrete endpoint/auth/webhook details
- [ ] OpenClaw reuses Phase 08 ACP components where applicable
- [ ] Extension manifest works
- [ ] Local plug commands work
- [ ] Permission validation works
- [ ] Tests pass
- [ ] v2 definition of done reviewed

## Suggested Next Prompt

`Implement Phase 11 only: channel adapters, OpenClawAdapter built on Phase 08 ACP foundation, and extension/plugin system. If OpenClaw API docs are missing, create the interface and mock tests only. Reuse ACPClient, ACPRegistryAdapter, and session management from Phase 08.`
