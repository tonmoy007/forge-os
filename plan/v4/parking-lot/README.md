# Parking Lot

Documents in this directory are **frozen out of the active v4 spec** pending the strategic decision recorded in `/STATUS.md` at the repo root.

## Policy

The v4 spec cannot grow while v4 is mid-implementation. New scope additions, vendor decisions, or architectural pivots discovered during implementation should be:

1. Captured here so the thinking isn't lost.
2. **Not** treated as build inputs by Phase 09+ implementation work.
3. Re-opened only when the strategic question in `STATUS.md` is resolved (continue v4 / extract Fork A / archive as research).

## Currently parked

| File | Date parked | Reason |
|---|---|---|
| `IMPORTANT_UPDATE.md` | 2026-05-13 | Proposes T-034..T-037 (CocoIndex MCP integration, ClawVault-inspired workers, Ruflo-inspired swarm mode). The CocoIndex BUY decision contradicts `tasks/lessons.md` L004 (CocoIndex requires PostgreSQL, rejected). The "INSPIRE" tracks (vault workers, swarm) add ~3-4 weeks of new scope before existing v4 work is complete. |
| `SRSv4.1ADDON.md` | 2026-05-13 | Adds Microsoft Agent Governance Toolkit (FR-AGT-001..012) and OpenSpec (FR-OS-001..008) as substrate dependencies. ADDON mappings (lines 27-36) replace the core Sandbox Manager / Credential Proxy / Health Daemon with AGT equivalents — turning ADR-006 "optional layers" into mandatory infrastructure. Cannot be merged into v4.1 without an ADR amendment and an explicit re-staffing decision. |

## Re-opening rule

Move a file back to `plan/v4/` **only** when:
1. `STATUS.md` resolves to "continue v4 expansion" (not "extract Fork A" or "archive").
2. The contradictions noted in the parking entry above are reconciled (e.g. AGT mandatory vs. ADR-006 optional).
3. A capacity check in `STATUS.md` confirms the team can absorb the additional scope.
