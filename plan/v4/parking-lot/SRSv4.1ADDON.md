# Forge OS — SRS Addendum v4.1  
**Agent Governance Toolkit (AGT) & OpenSpec Integration**

This addendum defines new functional requirements and architectural mappings that integrate **Microsoft Agent Governance Toolkit (AGT)** as the deterministic policy enforcement and zero‑trust identity substrate, and **OpenSpec by Fission‑AI** as the lightweight, spec‑first developer experience layer within the Forge OS ecosystem. These enhancements adopt production‑grade, open‑source solutions that fill critical gaps identified in the v4.0 design without duplicating effort.

---

## New Functional Requirements

### 3.25 AGT Integration — Deterministic Policy Enforcement & Zero‑Trust Identity

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑AGT‑001 | **Policy Engine Backend.** Forge OS shall use AGT’s Agent OS Policy Engine as the deterministic policy enforcement point for every agent tool call. Policies are expressed in YAML, with optional OPA/Rego for advanced rules. | Every tool invocation passes through AGT’s evaluator. Policies rejecting a tool call return an immediate denial before execution. Latency overhead <0.1ms per call. |
| FR‑AGT‑002 | **Policy Sync.** Forge OS stage‑level tool profiles (`pipeline/stages.yaml`) shall be automatically translated into AGT policies on stage entry. | Changing allowed tools for the Builder agent updates the active AGT policy set within the session without manual intervention. |
| FR‑AGT‑003 | **Capability Sandboxing.** Instead of Forge OS’s custom tool categorization, AGT’s POSIX‑inspired capability model shall be used. Each agent is granted a set of capabilities (e.g., `FS_READ`, `FS_WRITE`, `NET_BIND`, `PROC_EXEC`) scoped to its stage. | Capability violations are blocked deterministically. Policies may be `strict`, `permissive`, or `audit`‑only. |
| FR‑AGT‑004 | **Zero‑Trust Identity.** Every Forge OS agent shall be issued an Ed25519 identity via AGT’s AgentMesh, with SPIFFE/SVID certificates. | Agent identities are verifiable across sessions and across different kernel backends. Trust scores are maintained. |
| FR‑AGT‑005 | **Inter‑Agent Communication Security.** All messages between agents (including Ruflo Queen‑Worker communication) shall be encrypted and authenticated using AGT’s encrypted channels with mutual TLS and trust gates. | Inter‑agent messages cannot be intercepted or spoofed. Unauthorized agents are rejected. |
| FR‑AGT‑006 | **Execution Rings.** Forge OS shall adopt AGT’s 4‑tier execution ring model: Ring 0 (kernel/health daemon), Ring 1 (system agents: Reflector, Gate Checker), Ring 2 (stage agents), Ring 3 (untrusted/sandboxed code). | Ring transitions require explicit privilege checks. Agents in lower rings cannot invoke tools of higher rings. |
| FR‑AGT‑007 | **Circuit Breakers & SLOs.** AGT’s Agent SRE module shall be activated for long‑running stages (Build, Eval). Circuit breakers open after configurable error thresholds; SLOs (error budgets) are tracked. | When a circuit breaker opens, the stage is paused and the HITL Manager is notified. Automated retries are limited by error budget. |
| FR‑AGT‑008 | **Kill Switch.** AGT’s runtime termination control shall be integrated. A `forge agent kill <agent_id>` command immediately terminates the agent, revokes its identity, and saves a checkpoint. | Rogue agent detection (via anomaly scoring) may trigger automatic termination with audit record. |
| FR‑AGT‑009 | **MCP Security Scanning.** Before any community MCP server is loaded into Forge OS’s MCP Host, it shall be scanned by AGT’s MCP Security Scanner for tool poisoning, typosquatting, and hidden instructions. | Suspicious servers are rejected; warnings are logged and shown to the user. |
| FR‑AGT‑010 | **OWASP Compliance Verification.** A `forge verify --compliance owasp` command shall invoke AGT’s verification suite against the current pipeline configuration and agent fleet. | Report output shows pass/fail per OWASP Agentic Top 10 control; CI integration possible. |
| FR‑AGT‑011 | **Shadow AI Discovery.** AGT’s shadow discovery module shall periodically scan for unregistered AI agents interacting with the project’s resources. | Any found agent is reported in the health dashboard with a risk score. |
| FR‑AGT‑012 | **AGT Telemetry Integration.** AGT’s governance metrics (policy evaluations, denials, trust score changes, circuit breaker events) shall be exported to Forge OS’s OpenTelemetry pipeline and appear in the Audit Ledger. | Governance events are indistinguishable from native Forge OS audit entries. |

**Mapping to Existing Forge OS Components:**

| Forge OS v4.0 Component | Replaced/Augmented by AGT |
|--------------------------|----------------------------|
| Sandbox Manager (custom YAML tool profiles) | AGT Policy Engine + Capability Sandboxing |
| Credential Proxy (scoped session tokens) | AGT Zero‑Trust Identity (Ed25519, SPIFFE) |
| Phase‑Based Access Control (manual enforcement) | AGT Execution Rings (deterministic, OPA‑backed) |
| Health Daemon (self‑testing) | AGT Agent SRE (circuit breakers, SLOs, chaos) |
| MCP Host (trust on install) | AGT MCP Security Scanner (pre‑load audit) |
| Audit Ledger (manual policy events) | AGT Telemetry (all governance events auto‑logged) |

---

### 3.26 OpenSpec Integration — Lightweight Spec‑Driven Development

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OS‑001 | **OpenSpec as Spec Hub.** Forge OS shall treat the `openspec/` directory as the primary living specification for the project. The `openspec/specs/` folder contains the current source of truth; `openspec/changes/` contains active proposals. | Existing pipeline artifacts (`pipeline/01‑srs/`, etc.) are mirrored or linked to OpenSpec specs where applicable. |
| FR‑OS‑002 | **Lightweight Proposal Command.** A `/forge:propose <description>` command (or alias to `/opsx:propose`) shall create a new OpenSpec change with proposal, specs, design, and tasks. | The change appears in `openspec/changes/` and is visible in `forge status`. |
| FR‑OS‑003 | **Bidirectional Pipeline Sync.** When a Forge OS stage agent (e.g., System Architect) produces output, the relevant OpenSpec specs shall be updated. Conversely, an OpenSpec change approved by the user can auto‑populate Forge OS stage inputs. | No duplication; changes propagate in real time. |
| FR‑OS‑004 | **Fluid Stage Entry for OpenSpec Changes.** For changes initiated via OpenSpec, Forge OS shall offer a “fast path” that skips heavyweight SRS/Product/Architecture stages if the OpenSpec proposal already contains sufficient detail (as judged by the Findings Router). | A simple UI toggle allows users to “promote” a lightweight OpenSpec change to a full pipeline when needed. |
| FR‑OS‑005 | **OpenSpec Change as Feedback Intake.** Feedback submissions (Stage 10) may be automatically converted into OpenSpec changes if they describe a desired feature or fix. | A Triage agent option “Create OpenSpec proposal” is available; saves manual scaffolding. |
| FR‑OS‑006 | **Archive → Learning Loop.** When an OpenSpec change is archived (`/opsx:archive`), Forge OS’s Lesson Extractor shall process the change history (specs, tasks, test results) and extract structured lessons into the LKG. | Each archived change yields at least one reflection entry and may generate new lessons. |
| FR‑OS‑007 | **OpenSpec Schema for Forge OS.** Forge OS shall publish a community OpenSpec schema (`forge-os`) that defines artifact sequences tailored for Forge OS projects (e.g., required sections for architecture specs, traceability tags). | Using `--schema forge-os` with OpenSpec enforces Forge OS artifact standards. |
| FR‑OS‑008 | **Multi‑Change Parallelism.** Forge OS shall respect OpenSpec’s ability to work on multiple changes simultaneously. The pipeline state may track multiple active proposals, and agents shall be able to context‑switch between them. | No forced sequential locking; parallel feature work is natively supported. |

**Mapping to Existing Forge OS Components:**

| Forge OS v4.0 Component | Enhanced by OpenSpec |
|--------------------------|----------------------|
| Stage 1 (SRS) & Stage 4 (Spec) | Can be seeded or replaced by OpenSpec proposals for appropriate work items |
| Backtrack & Rework (FR‑BT) | OpenSpec’s delta‑based changes make rework scoping easier |
| Feedback Intake (Stage 10) | Convert feedback directly into structured OpenSpec changes |
| Lesson Extraction | Archive events feed richer context into the LKG |

---

## Impact on Existing SRS Sections

- **Section 3.4 (Gate Enforcement)** : Merge gates (FR‑GT‑006) can now be enforced by AGT policy: only branches with passing gate results may merge; AGT’s policy engine blocks premature merges.
- **Section 3.7 (Backtrack)** : OpenSpec changes that modify upstream specs automatically flag downstream artifacts via the ADG, strengthening the backtrack trigger.
- **Section 3.11 (Background Vault Workers)** : The Surveyor worker can leverage OpenSpec’s change history to detect cross‑project patterns.
- **Section 3.17 (Layered Sandbox Security)** : AGT’s execution rings replace the manual phase‑based access control, providing deterministic separation.
- **Section 3.22 (Observability & Audit)** : AGT telemetry feeds directly into the dual‑stream OpenTelemetry tracing and the audit ledger.

---

## Updated Implementation Roadmap

| Phase | AGT Integration Effort | OpenSpec Integration Effort |
|-------|------------------------|----------------------------|
| **Phase 2** (Agents & Gates) | Replace tool permission checks with AGT policy engine calls (2 weeks) | Add `/forge:propose` command and bidirectional sync (2 weeks) |
| **Phase 3** (Memory) | Feed AGT policy evaluations into the Audit Ledger (1 week) | Archive OpenSpec changes → LKG lesson extraction (1 week) |
| **Phase 4** (Always‑On) | Activate AGT Agent SRE circuit breakers for daemon (1 week) | — |
| **Phase 5** (Channels) | Use AGT identities for channel‑authenticated agents (1 week) | — |
| **Phase 6** (Hardening) | Full integration: execution rings, MCP scanner, OWASP CI (3 weeks) | Publish community OpenSpec schema; full bidirectional sync (2 weeks) |

---

## Verification

- **AGT Integration Test:** Simulate an agent attempting to use a disallowed tool; the AGT policy engine returns a denial logged in both AGT’s telemetry and Forge OS’s audit ledger.
- **OpenSpec Integration Test:** Run `/forge:propose "add user auth"` → verify OpenSpec change created → start a lightweight build via `/forge:apply` (delegating to Stage 6 fast path) → archive and observe lesson extracted.

---

This addendum, combined with the v4.0 SRS, defines a Forge OS that is secured by a battle‑tested governance toolkit and streamlined by a developer‑friendly spec workflow, without sacrificing the depth, memory, or self‑improvement capabilities of the core system.
