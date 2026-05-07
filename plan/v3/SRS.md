# Software Requirements Specification  
## Forge OS – Self‑Sustaining Software Engineering Ecosystem  
**Version 3.0 – Enterprise‑Ready**  
**Date:** 2026‑05‑07  
**Author:** Forge OS Architecture Team  

---

## Table of Contents
1. [Introduction](#1-introduction)  
   1.1 [Purpose](#11-purpose)  
   1.2 [Scope](#12-scope)  
   1.3 [Definitions, Acronyms, and Abbreviations](#13-definitions-acronyms-and-abbreviations)  
   1.4 [References](#14-references)  
   1.5 [Overview](#15-overview)  
2. [Overall Description](#2-overall-description)  
   2.1 [Product Perspective](#21-product-perspective)  
   2.2 [Product Functions](#22-product-functions)  
   2.3 [User Characteristics](#23-user-characteristics)  
   2.4 [Operating Environment](#24-operating-environment)  
   2.5 [Design and Implementation Constraints](#25-design-and-implementation-constraints)  
   2.6 [Assumptions and Dependencies](#26-assumptions-and-dependencies)  
3. [System Features (Functional Requirements)](#3-system-features-functional-requirements)  
   3.1 [Orchestration Engine & SDLC Pipeline](#31-orchestration-engine--sdlc-pipeline)  
   3.2 [Kernel Adapter Layer](#32-kernel-adapter-layer)  
   3.3 [Specialized Agent System](#33-specialized-agent-system)  
   3.4 [Gate Enforcement & Quality Evaluation](#34-gate-enforcement--quality-evaluation)  
   3.5 [Memory & Learning Subsystem](#35-memory--learning-subsystem)  
   3.6 [Artifact Dependency Graph & Context Pruning](#36-artifact-dependency-graph--context-pruning)  
   3.7 [Backtrack & Rework Automation](#37-backtrack--rework-automation)  
   3.8 [Health & Sustainability Daemon](#38-health--sustainability-daemon)  
   3.9 [Gradual Onboarding & Adaptation](#39-gradual-onboarding--adaptation)  
   3.10 [Cross‑Project Global Memory](#310-cross‑project-global-memory)  
   3.11 [Background Daemon & Always‑On Monitoring](#311-background-daemon--always‑on-monitoring)  
   3.12 [Dreamer Agent & Passive Knowledge Consolidation](#312-dreamer-agent--passive-knowledge-consolidation)  
   3.13 [Lazy Context Builder](#313-lazy-context-builder)  
   3.14 [Channel Adapter Layer](#314-channel-adapter-layer)  
   3.15 [Layered Sandbox Security](#315-layered-sandbox-security)  
   3.16 [Extension Ecosystem](#316-extension-ecosystem)  
   3.17 [OpenClawAdapter](#317-openclawadapter)  
   3.18 [Human‑in‑the‑Loop Governance](#318-human‑in‑the‑loop-governance)  
   3.19 [End‑to‑End Observability & Audit](#319-end‑to‑end-observability--audit)  
   3.20 [Token Economics & Cost Management](#320-token-economics--cost-management)  
4. [External Interface Requirements](#4-external-interface-requirements)  
   4.1 [User Interfaces](#41-user-interfaces)  
   4.2 [Hardware Interfaces](#42-hardware-interfaces)  
   4.3 [Software Interfaces](#43-software-interfaces)  
   4.4 [Communication Interfaces](#44-communication-interfaces)  
5. [Non‑Functional Requirements](#5-non‑functional-requirements)  
   5.1 [Performance](#51-performance)  
   5.2 [Reliability](#52-reliability)  
   5.3 [Availability](#53-availability)  
   5.4 [Security](#54-security)  
   5.5 [Maintainability & Extensibility](#55-maintainability--extensibility)  
   5.6 [Portability](#56-portability)  
   5.7 [Usability](#57-usability)  
   5.8 [Observability & Audit](#58-observability--audit)  
6. [Appendix A: SDLC Stage Definitions](#6-appendix-a-sdlc-stage-definitions)  
7. [Appendix B: Gate Criteria Examples](#7-appendix-b-gate-criteria-examples)  
8. [Appendix C: Glossary](#8-appendix-c-glossary)  

---

## 1. Introduction

### 1.1 Purpose
Forge OS is a **standalone, self‑sustaining software engineering ecosystem** that orchestrates the complete 12‑stage SDLC through a pipeline of specialised AI agents, multi‑modal quality gates, and a continuous cross‑project learning memory system. This SRS defines the functional and non‑functional requirements for Forge OS **Version 3.0**, which incorporates enterprise‑grade security sandboxing, structured human‑in‑the‑loop governance, immutable audit trails, and comprehensive observability.

### 1.2 Scope
Forge OS V3 encompasses:
- A full 12‑stage extensible SDLC pipeline with automated state transitions.
- 16 specialised AI agents with persona‑based tool restrictions and scoped contexts.
- Multi‑modal gate enforcement including sandboxed external commands and metric thresholds.
- A three‑tier graph‑based memory architecture (Lessons Knowledge Graph, Artifact Dependency Graph).
- A self‑learning loop (reflection, lesson extraction, skill mining, dream consolidation).
- Enterprise‑grade security: gVisor sandboxing, phase‑based access control, credential proxy.
- Structured Human‑in‑the‑Loop (HITL) governance with risk‑based escalation and cryptographic signing.
- Dual‑stream OpenTelemetry tracing and an immutable append‑only audit ledger.
- Token economics monitoring and cost attribution.
- Kernel‑agnostic architecture with adapters for Claude, GPT, OpenClaw, and local models.
- Gradual adoption profiles (`minimal`, `standard`, `expert`).
- A community‑pluggable extension ecosystem via the MCP protocol.

### 1.3 Definitions, Acronyms, and Abbreviations
- **ADG**: Artifact Dependency Graph – a directed graph linking pipeline artifacts (e.g., spec depends on architecture).  
- **Audit Ledger**: An immutable append‑only log of all significant events (gate advances, HITL decisions, tool calls).  
- **Capsule**: A token‑optimised context unit containing full or skeleton versions of artifacts.  
- **Dreamer Agent**: An asynchronous agent that consolidates daily logs, checks for knowledge contradictions, and applies lesson decay.  
- **gVisor**: A user‑space kernel that provides container isolation with a small attack surface.  
- **HITL**: Human‑in‑the‑Loop – structured checkpoints where a human must approve, choose, or provide feedback.  
- **Kernel**: The underlying AI execution environment (Claude, GPT, OpenClaw, local LLM).  
- **LKG**: Lessons Knowledge Graph – a graph of learned rules with confidence, relationships, and temporal data.  
- **MCP**: Model Context Protocol – a standard for connecting AI agents to external tools and memory.  
- **OTLP**: OpenTelemetry Protocol – used for exporting traces, metrics, and logs.  
- **Sandbox**: A restricted execution environment (gVisor container) that prevents unauthorised access.  
- **Two‑Key Rule**: A security principle requiring two separate identities for initiation and approval of critical actions.

### 1.4 References
- Forge OS Architecture Overview v3 (internal)  
- IEEE 830‑1998 – Recommended Practice for Software Requirements Specifications  
- OpenClaw Security Documentation  
- OWASP Top 10 for LLM Applications  
- W3C Agentic Integrity Verification Specification (draft)  

### 1.5 Overview
Section 2 describes the high‑level system context. Section 3 enumerates all functional requirements grouped by subsystem. Section 4 specifies external interfaces. Section 5 covers non‑functional requirements. Appendices provide reference material.

---

## 2. Overall Description

### 2.1 Product Perspective
Forge OS is a distributed, local‑first system that can operate entirely on a developer’s machine or scale to a team server. It interfaces with:
- AI kernels through a standardised Kernel Adapter Layer.
- External tools (test runners, linters, security scanners) via MCP servers or sandboxed commands.
- Human stakeholders via CLI, web dashboard, and messaging channels (through the Channel Adapter Layer).
- An immutable filesystem store for all pipeline artifacts, knowledge graphs, and audit logs.

### 2.2 Product Functions
- Automate the entire software lifecycle from requirements to post‑release retrospectives.
- Enforce quality gates at every stage using a mix of deterministic checks and AI review.
- Learn from user corrections, repeated patterns, and cross‑project experience to continuously improve.
- Provide full visibility into every decision, tool call, and stage transition.
- Ensure security through least‑privilege sandboxes and separation of duties.
- Allow safe delegation of high‑risk actions to humans through structured approval workflows.
- Scale from a single developer using a 3‑stage pipeline to an enterprise team with full governance.

### 2.3 User Characteristics
- **Primary**: Software developers and engineers at any experience level.
- **Secondary**: Technical leads and project managers who monitor pipeline health and enforce governance.
- **Tertiary**: Compliance officers who audit the development process.
- **Quaternary**: Community contributors who extend agents, gates, or profiles.

### 2.4 Operating Environment
- **OS**: Linux (primary), macOS, Windows (via WSL2 for sandboxing).  
- **Runtime**: Python 3.12+ with optional Node.js for some MCP servers.  
- **Storage**: Local filesystem (standard profiles: SQLite, Git‑versioned artifacts); optional external Neo4j/PostgreSQL for graph memory.  
- **Container Runtime**: gVisor `runsc` for sandboxed execution (optional in `minimal` profile).  
- **Network**: Required only for remote AI kernels and community extensions; all core pipeline logic works offline.

### 2.5 Design and Implementation Constraints
- All persistent data shall be in open, human‑readable formats (Markdown, YAML, JSON, GraphML) to avoid vendor lock‑in and enable Git‑based version control.
- The system must be modular: every component (agent, gate, kernel adapter, MCP server) is replaceable via a defined interface.
- The Kernel Adapter Layer shall be language‑agnostic, allowing any AI backend to be plugged in.
- The audit ledger shall be immutable and verifiable via cryptographic HMAC chaining.

### 2.6 Assumptions and Dependencies
- The user has access to at least one AI kernel (local or remote) for agent operation.
- External tools (test runners, linters) are available in the execution environment or can be containerised.
- The filesystem is reliable; no transactional database is required for core operation.
- The gVisor runtime is installed for sandboxed execution (in `standard` and `expert` profiles).

---

## 3. System Features (Functional Requirements)

### 3.1 Orchestration Engine & SDLC Pipeline  
*(Preserved from V2 – FR‑OE‑001 to FR‑OE‑005 unchanged)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OE‑001 | Pipeline state machine maintaining 12 extensible stages and valid transitions. | Transitions are verified against gate results; state persisted atomically. |
| FR‑OE‑002 | CLI commands to start any stage (`forge stage start <name>`). | Blocked if previous gate not met; forced override available with audit trail. |
| FR‑OE‑003 | Lifecycle hooks: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd`. | Hooks execute in defined order; failure logged but does not crash session. |
| FR‑OE‑004 | Asynchronous agent dispatch with progress tracking. | Multiple agents can run concurrently if stage logic permits. |
| FR‑OE‑005 | `forge resume` and `forge status` restore exact session context and show pipeline progress. | Resume after restart provides identical context; status reflects real‑time state. |

### 3.2 Kernel Adapter Layer  
*(FR‑KA‑001 to FR‑KA‑004 from V2, updated for capability introspection)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑KA‑001‑v3 | Abstract `IKernelAdapter` interface with `get_capabilities()`, `spawn_agent()`, `on_event()`, `sync_memory()`. | All kernel adapters implement the interface; community can add new adapters. |
| FR‑KA‑002‑v3 | Capability introspection: adapter reports available tools, MCP servers, agent types, and hook support. | Forge OS Capability Manager merges this with stage requirements to build a final tool allowlist. |
| FR‑KA‑003 | Tool mapping: abstract tool permissions (Read, Write, Bash) translated to kernel‑specific implementations. | Kernel’s native function‑calling respects the allowed tool set. |
| FR‑KA‑004 | Lifecycle event bridging: adapter translates kernel‑native events (PrefToolUse, Stop) into standard Forge OS events. | All hooks fire identically regardless of kernel. |

### 3.3 Specialized Agent System  
*(FR‑AG‑001 to FR‑AG‑004, expanded to cover 16 agents)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑AG‑001‑v3 | 16 agent personas: 12 stage agents + 4 cross‑stage agents (Reflector, Lesson Extractor, Skill Miner, Gate Checker). | Each persona defined in a YAML file with role, goal, tool permissions, output contract. |
| FR‑AG‑002 | Context injection before spawning agent; only relevant artifacts from ADG and high‑confidence lessons injected. | Token count under configured budget; context identical on resume. |
| FR‑AG‑003‑v3 | Agent‑specific tool restrictions enforced by Kernel Adapter AND sandbox policy. | Builder agent cannot execute `Bash` outside sandbox; Architect cannot write to source directories. |
| FR‑AG‑004 | Output contract enforcement: after agent completes, Gate Checker verifies required artifacts exist. | Missing artifact fails the stage gate. |

### 3.4 Gate Enforcement & Quality Evaluation  
*(FR‑GT‑001 to FR‑GT‑005, enhanced with risk levels)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑GT‑001‑v3 | Multi‑modal gate criteria types: `FileExistence`, `PatternMatch`, `LLMReview`, `ExternalCommand`, `MetricThreshold`. Each criterion carries a risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). | Criteria evaluated in parallel; results aggregated into a `GateReport`. |
| FR‑GT‑002‑v3 | Gate check on stage advance: if advance mode is `strict`, any failed non‑optional criterion blocks advancement. | Blocked stages display unmet criteria and remediation tips. |
| FR‑GT‑003 | In‑session nudge for design system violations via `PreToolUse` hook. | Agent receives contextual feedback without blocking. |
| FR‑GT‑004‑v3 | ExternalCommand criteria execute inside gVisor sandbox (see 3.15). | Sandbox ensures no host file access, no network egress (unless allowlisted). |
| FR‑GT‑005 | Gate criteria versioned and stored in `pipeline/gates.yaml`; changes logged. | Audit trail records who changed which criterion and when. |

### 3.5 Memory & Learning Subsystem  
*(Combined V2 memory requirements with graph‑based LKG)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ML‑001‑v3 | Three‑tier memory: Tier‑1 (session context), Tier‑2 (project graph store: LKG + ADG), Tier‑3 (global cross‑project). | Lessons promoted to Tier‑3 after use in ≥3 projects with confidence >0.8. |
| FR‑ML‑002‑v3 | Lesson Extractor agent: parses user corrections and “remember this” statements → creates structured lesson nodes in LKG. | Each lesson has trigger, rule, confidence, stage tags, and source. |
| FR‑ML‑003‑v3 | Lesson confidence model: initial confidence 0.9 (explicit) / 0.5 (inferred); decays over time if unused; dormant below 0.3. | Dreamer Agent applies decay; dormant lessons excluded from context injection. |
| FR‑ML‑004 | Reflector Agent: after every `Stop`, compares output to gate criteria, logs reflection and quality rating. | Reflection stored in pipeline state; influences subsequent agent prompts. |
| FR‑ML‑005‑v3 | Skill Miner: tracks repeated action sequences; when frequency ≥3, generates a skill definition (SKILL.md) and optionally an MCP server scaffold. | User approves or rejects; approved skills become invocable commands. |
| FR‑ML‑006‑v3 | Knowledge Graph maintenance: detect duplicate/contradictory lessons using LKG community detection algorithms (e.g., Leiden). | Dreamer report includes proposed merges/retirements. |

### 3.6 Artifact Dependency Graph & Context Pruning  
*(FR‑ADG‑001 to FR‑ADG‑003, enhanced with Vexp‑style capsule building)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ADG‑001‑v3 | ADG builder extracts dependencies from pipeline artifact declarations and code analysis (Vexp‑style). | Graph includes edges like `GENERATED_FROM`, `INFLUENCES`; persisted as GraphML. |
| FR‑ADG‑002‑v3 | Context Pruner: spread‑activation from required artifacts, scored by BM25, graph distance, recency, lesson relevance. Greedy fill token budget; “capsules” (skeleton) for mid‑scored artifacts. | Token budget respected; relevance score measurable; skeleton context reduces waste by >60% vs. full dump. |
| FR‑ADG‑003 | Staleness detection: when upstream artifact is modified, ADG marks downstream nodes as `potentially_stale`. | `forge status` warns of stale artifacts; backtrack tickets created automatically. |

### 3.7 Backtrack & Rework Automation  
*(FR‑BT‑001 to FR‑BT‑003 unchanged from V2)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑BT‑001 | Feed‑Forward Propagation Engine creates backtrack tickets when late‑stage findings impact upstream artifacts. | Tickets list affected stages derived from ADG. |
| FR‑BT‑002 | Rework cascade generation: revisits affected stages in order with “diff mode” agents. | User approves cascade; only changed artifacts are reprocessed. |
| FR‑BT‑003 | Minimal rework: only truly affected artifacts reprocessed; unmodified derivatives are not regenerated. | Rework does not duplicate unchanged work. |

### 3.8 Health & Sustainability Daemon  
*(FR‑HD‑001 to FR‑HD‑005 from V2, now integrated with Dreamer and audit)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑HD‑001‑v3 | Health Daemon runs hook unit tests, gate simulations, and knowledge integrity checks on schedule. | Failures reported in health dashboard; automatic disabling of consistently failing hooks enabled. |
| FR‑HD‑002‑v3 | Knowledge integrity: scan LKG for contradictions, extremely low confidence, stale references to missing artifacts. | Results included in daily/weekly health report. |
| FR‑HD‑003‑v3 | Token budget monitoring extended to Token Economics Dashboard (see 3.20). | Alerts when actual usage exceeds budget by 20%. |
| FR‑HD‑004‑v3 | System evolution proposals: after configurable cycles, daemon may propose pipeline improvements (new gates, adjusted criteria). | Proposals presented as diffable PRs against `pipeline/stages.yaml`. |
| FR‑HD‑005 | Hook latency overshoot: if hook execution consistently exceeds threshold, daemon flags it for optimisation. | Persistent offenders auto‑disabled after notification. |

### 3.9 Gradual Onboarding & Adaptation  
*(FR‑ON‑001 to FR‑ON‑004 unchanged from V2)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ON‑001 | Profile levels: `minimal` (3 stages), `standard` (12 stages), `expert` (custom). | User selects on init; upgrade preserves existing artifacts. |
| FR‑ON‑002 | Onboarding wizard: guided first cycle with explanations. | Reduces cognitive load; skippable. |
| FR‑ON‑003 | Gradual feature unlock: advanced features remain dormant until user completes two cycles. | Opt‑in activation with benefits explained. |
| FR‑ON‑004 | Context‑sensitive help: `forge explain <topic>` retrieves stage‑relevant information. | Draws from project memory and global references. |

### 3.10 Cross‑Project Global Memory  
*(FR‑GLOB‑001 to FR‑GLOB‑003 unchanged from V2, now backed by graph)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑GLOB‑001 | Global lesson promotion when confidence >0.8 and used in ≥3 projects. | Requires explicit user approval; tagged with source projects. |
| FR‑GLOB‑002 | Global skill library: skills validated across projects moved to `~/.forge/skill-library/`. | Maintains versioning; can be centrally updated. |
| FR‑GLOB‑003 | Project profiles memory: learning preferred stacks, conventions per project. | Stored in `~/.forge/project-profiles.yaml`; user editable. |

### 3.11 Background Daemon & Always‑On Monitoring  
*(New in V3 – from OpenClaw enhancements)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑BD‑001 | `forge daemon start` launches a background process that survives logouts. | Process manageable via systemd or equivalent; resumes gracefully after host reboot. |
| FR‑BD‑002‑v3 | Always‑On Observer agent: for projects at Stage 9+, monitors deployed endpoints; alerts on anomalies. | Alerts appear in CLI, status dashboard, and channel adapters. |
| FR‑BD‑003 | Scheduled Dreamer cycles (nightly) for knowledge consolidation. | Dreamer runs without human intervention; produces morning report. |

### 3.12 Dreamer Agent & Passive Knowledge Consolidation  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑DR‑001 | Daily SDLC digest generation: summarises sessions, decisions, reflections into date‑stamped files. | Digest created if any activity occurred. |
| FR‑DR‑002‑v3 | REM re‑ingestion: periodically re‑reads old reflections and ADR’s, checks for contradictions with current LKG. | Contradictions flagged as “tensions” for human review. |
| FR‑DR‑003‑v3 | Lesson decay application: Dreamer applies confidence decay function to all lessons, marks dormant below 0.3. | Dormant lessons excluded from Tier‑1 injection. |
| FR‑DR‑004‑v3 | Duplicate & conflict detection using LKG community detection (Leiden algorithm). | Proposed merges presented in morning report; user approves. |

### 3.13 Lazy Context Builder  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑LCB‑001 | Agent initial context includes a menu of available skills (one‑line descriptions) and high‑confidence lessons only. | Token count for initial context ≤50% of total budget. |
| FR‑LCB‑002 | On‑demand loading: when agent selects a skill, full instructions injected in a subsequent context update. | Update is synchronous and human‑transparent. |
| FR‑LCB‑003 | Lazy lesson loading: low‑confidence lessons listed in an index; agent can request expansion. | Request returns full lesson details. |
| FR‑LCB‑004 | Token budget guard: loader refuses to load a full skill if it would exceed remaining budget; prompts agent to free context first. | Warning logged; agent receives instruction to summarise previous work. |

### 3.14 Channel Adapter Layer  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑CH‑001 | Abstract channel adapter interface: `send_message()` and `on_incoming()`. | Accepts any channel implementation. |
| FR‑CH‑002 | Feedback intake: messages on configured channels can create feedback items for Stage 10. | Triage agent picks up feedback; untrusted input handled safely. |
| FR‑CH‑003 | Status query: user can ask `@forge status` in a channel and receive a human‑readable pipeline summary. | Response respects channel formatting limits. |
| FR‑CH‑004 | Release broadcast: Release Manager agent pushes release notes to all configured channels. | Uses the channel adapter’s send method. |

### 3.15 Layered Sandbox Security  
*(New in V3 – replaces and extends original FR‑SEC)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑SEC‑001‑v3 | Phase‑Based Access Control: agents are limited by their SDLC phase. Contract writers (Stages 1‑5) cannot access `Bash` or source directories; implementers (Stage 6) cannot modify upstream artifacts; validators (Stage 7) are read‑only. | Enforcement at tool‑call and filesystem level; violations blocked and logged. |
| FR‑SEC‑002‑v3 | gVisor Kamikaze Sandbox: all `ExternalCommand` gates and agent `Bash` calls run inside ephemeral gVisor containers with no network, dropped capabilities, and auto‑destroy after 30s. | Test: agent tries to `curl` external URL → blocked; container filesystem discarded. |
| FR‑SEC‑003‑v3 | Credential Proxy: agent containers never hold raw secrets; a sidecar injects scoped `FORGE_SESSION_TOKEN`. | Token is short‑lived and restricted to the current stage’s resources. |
| FR‑SEC‑004‑v3 | Four‑Layer Defense Profile: each agent profile defines `sandbox_runtime`, `network_policy`, `credential_scope`, and `prompt_integrity` enforcement. | Agents cannot bypass layers or escalate privileges. |
| FR‑SEC‑005‑v3 | Untrusted Input Marking: all user feedback and channel messages are wrapped in a metadata envelope indicating source and trust level. | Prompt integrity framework prevents injection. |

### 3.16 Extension Ecosystem  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑EXT‑001‑v3 | Four pluggable extension points: Kernel Adapters, Stage Agents, Gate Criteria Modules, Profile Packs. All must implement published MCP or interface schemas. | Validation tool checks compliance before installation. |
| FR‑EXT‑002‑v3 | `forge plug` CLI: search, install, update, remove extensions from a registry. | Installed extensions activated after config reload; conflicts detected. |
| FR‑EXT‑003 | Extensions run with same sandbox restrictions as core agents; cannot override state machine or audit log. | Permissions declared in extension manifest. |

### 3.17 OpenClawAdapter  
*(New in V3 – formalises the earlier kernel adapter spec)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OCA‑001 | Adapter translates Forge OS agent persona, context, and tool policy into OpenClaw agent configuration (SOUL.md, IDENTITY.md) and starts a session via Gateway API. | Agent starts within 5 seconds. |
| FR‑OCA‑002 | Tool mapping: Forge OS tool categories mapped to OpenClaw’s tool‑use policy (Allowlist/Denylist). | Tool restrictions enforced by OpenClaw native sandbox. |
| FR‑OCA‑003 | Lifecycle bridging: adapter subscribes to OpenClaw webhooks for agent completion and translates to Forge OS `Stop` events. | Reflection and gate check occur inside Forge OS immediately after agent stop. |
| FR‑OCA‑004 | Channel reuse: exposes OpenClaw’s existing channel connections to the Forge OS Channel Adapter Layer. | Feedback and status queries work seamlessly; no extra bot registration needed. |
| FR‑OCA‑005 | Memory separation: ensures Forge OS artifacts are source of truth; syncs any new insights back to `.forge/` after session. | OpenClaw native memory does not override pipeline state. |
| FR‑OCA‑006 | Offline fallback: if OpenClaw unreachable, notifies user and gracefully falls back to another kernel adapter. | State remains consistent; no data loss. |

### 3.18 Human‑in‑the‑Loop Governance  
*(New in V3 – replaces original HITL mention)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑HITL‑001‑v3 | Risk‑based routing: every gate is classified LOW, MEDIUM, HIGH, CRITICAL. LOW auto‑advances; MEDIUM shows notification with 30s override; HIGH pauses pipeline for structured HITL; CRITICAL enforces Two‑Key Rule. | All routing is auditable; user can see why an action was escalated. |
| FR‑HITL‑002‑v3 | Type‑aware decision rendering: `phase_gate` (artifact summary + gate results), `choice` (selectable options with diff preview), `feedback` (structured multi‑question form). Every checkpoint includes “General Feedback” and “Change Approach” options. | Rendered appropriately for CLI and web. |
| FR‑HITL‑003‑v3 | Maker‑Checker enforcement: approving identity must differ from initiating agent. No agent can approve its own stage advancement. | Self‑approval attempts logged and blocked; cryptographic signing ties decisions to identities. |
| FR‑HITL‑004 | Classifier‑assisted autonomy: an optional safety classifier can pre‑screen tool calls, auto‑approving safe ones and routing ambiguous/dangerous ones to HITL. | Classifier decisions themselves auditable. |
| FR‑HITL‑005‑v3 | Override trail: every forced advance or gate override records the reason, timestamp, and identity; downstream artifacts flagged as “human‑override”. | Health Daemon re‑evaluates those gates next cycle. |

### 3.19 End‑to‑End Observability & Audit  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OBS‑001‑v3 | Dual‑stream tracing: every session emits (a) reasoning spans (LLM calls, tool use, MCP), (b) runtime audit spans (file access, network, process execution). All correlated by `session_id` and exported via OTLP. | Dashboard shows both streams simultaneously. |
| FR‑OBS‑002‑v3 | Immutable audit ledger: `.forge/audit/ledger.jsonl` is append‑only; each entry contains a HMAC chain signature. `forge audit verify` validates integrity. | Tampering is detectable; genesis entry signed with project key. |
| FR‑OBS‑003‑v3 | Per‑session transcripts: write‑once log of all agent reasoning steps, tool inputs/outputs, and policy decisions. 100% sampling, no gaps. | Stored in `.forge/audit/sessions/`. |
| FR‑OBS‑004‑v3 | Artifact lineage tracking: every pipeline artifact carries YAML frontmatter with agent ID, session ID, dependencies, and version. | `forge artifact lineage <file>` shows full provenance. |
| FR‑OBS‑005‑v3 | Token Economics Dashboard: metrics for token consumption, cost per stage, context relevance score, waste %. | Aggregated in Prometheus/Grafana or built‑in CLI report. |
| FR‑OBS‑006‑v3 | Lesson & skill version history: every LKG node and skill keeps version and usage/success metrics. | Health Daemon can auto‑deprecate low‑usage or low‑success skills. |
| FR‑OBS‑007‑v3 | Audit query API: `forge audit query --risk=HIGH --stage=6` returns filtered, exportable results. | Supports compliance reporting. |

### 3.20 Token Economics & Cost Management  
*(New in V3)*  

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑TE‑001 | Token cost attribution: for each agent session, calculate token usage (prompt + completion) and translate to cost using kernel’s pricing. | Stored in audit ledger and aggregated in dashboard. |
| FR‑TE‑002 | Context relevance scoring: measure what percentage of injected context was actually referenced by the agent. | Used to tune the Context Pruner; low score triggers optimisation. |
| FR‑TE‑003 | Budget enforcement: per‑stage and per‑session token budgets configurable; warnings at 80%, errors at 100% (session may be paused). | Prevention of runaway token usage. |

---

## 4. External Interface Requirements

### 4.1 User Interfaces
- **CLI**: Primary interface; commands listed in Section 3. Output is plain text with optional JSON for machine consumption.
- **Web Dashboard (optional)**: Visual pipeline status, health reports, HITL queues, audit query interface.  
- **Channel UI**: Through configured channel adapters, users receive notifications and can submit commands/feedback.

### 4.2 Hardware Interfaces
None. Forge OS runs on commodity hardware.

### 4.3 Software Interfaces
- **Filesystem**: read/write `pipeline/`, `.forge/`, `~/.forge/`.
- **AI Kernels**: via the Kernel Adapter Layer (REST, gRPC, or plugin hooks).
- **MCP Servers**: standard MCP protocol (JSON‑RPC over stdio or HTTP).
- **OTLP Collector**: for traces and metrics export.
- **Sandbox Runtime**: gVisor `runsc` binary.
- **VCS (Git)**: for versioning of pipeline artifacts.

### 4.4 Communication Interfaces
- Internal event bus (in‑process for single‑user; Redis/MQ for team mode).
- MCP client communicates with external tool servers.
- Channel adapters communicate with messaging APIs (Telegram, Slack, etc.).

---

## 5. Non‑Functional Requirements

### 5.1 Performance
- Hook execution latency (excluding AI calls) < 200ms.
- Session context injection computed in < 500ms.
- Agent spawn time < 5 seconds (first session may include MCP server startup).
- Sandbox container start < 2 seconds.

### 5.2 Reliability
- Hook failures must not crash the session; errors logged, stage continues with warning.
- Gate checks must be idempotent.
- System survives crash or power loss without corrupting state (atomic writes).

### 5.3 Availability
- Core pipeline offline‑capable (local kernel or human adapter).
- Daemon and Dreamer are optional; pipeline runs without them.

### 5.4 Security
- Adherence to OWASP Top 10 for LLM Applications.
- gVisor sandbox with least privilege enforced.
- Credential proxy prevents secret leakage.
- All HITL decisions are cryptographically signed.
- Immutable audit ledger with HMAC chain.

### 5.5 Maintainability & Extensibility
- Modular architecture: all components hot‑swappable via interfaces.
- Configuration in versioned YAML with schema validation.
- Automated self‑testing via Health Daemon.

### 5.6 Portability
- Core engine runs on any Python 3.12+ environment.
- Kernel adapters replaceable without core changes.

### 5.7 Usability
- Onboarding wizard allows a new user to complete a first cycle (3‑stage) in < 30 minutes.
- All status messages in plain language.
- User can always override any gate (with audit).

### 5.8 Observability & Audit
- 100% of tool calls, gate evaluations, and HITL decisions are recorded in the audit ledger.
- Traces exportable to any OTLP‑compatible backend.
- Audit ledger verifiable offline.

---

## 6. Appendix A: SDLC Stage Definitions

*(Same as V2, unchanged)*  

| Stage | Purpose | Primary Agent |
|-------|---------|---------------|
| 1. SRS | Elicit and document software requirements | Requirements Analyst |
| 2. Product | Define user experience, design system, product decisions | Product Designer |
| 3. Architecture | Design system architecture, data models, API contracts | System Architect |
| 4. Spec | Write technical specification bridging architecture to code | Spec Writer |
| 5. Plan | Decompose into task DAG, milestones, risk register | Planner |
| 6. Build | Implement code and tests | Builder |
| 7. Eval | Evaluate against specs, run tests, audits | Evaluator |
| 8. Deploy | Deploy to staging/production | DevOps |
| 9. Monitor | Set up observability and monitor post‑deploy | Observer |
| 10. Feedback | Collect feedback, triage, and impact analysis | Triage |
| 11. Resolve | Address hotfixes, backlog updates | Resolver |
| 12. Release | Release final version, retrospective, documentation | Release Manager |

---

## 7. Appendix B: Gate Criteria Examples

*(Enhanced with risk levels)*  

**Stage 6 (Build):**
| Criterion | Type | Threshold | Risk |
|-----------|------|-----------|------|
| All DAG tasks “Done” | FileExistence | required | LOW |
| Unit test coverage > 80% | MetricThreshold | 80 | HIGH |
| Lint passes | ExternalCommand | exit 0 | MEDIUM |
| No raw CSS values | PatternMatch | must pass | LOW |
| All REQ‑IDs have test | LLMReview | manual review | MEDIUM |

**Stage 8 (Deploy):**
| Criterion | Type | Threshold | Risk |
|-----------|------|-----------|------|
| Staging deploy dry‑run | ExternalCommand | exit 0 | HIGH |
| Production deploy approval | HITL | explicit approval | CRITICAL |

---

## 8. Appendix C: Glossary

- **ADG**: Artifact Dependency Graph.  
- **Audit Ledger**: Append‑only record of significant events.  
- **Capsule**: A token‑optimised context unit.  
- **Dreamer Agent**: Offline consolidation agent.  
- **gVisor**: User‑space kernel for sandboxing.  
- **HITL**: Human‑in‑the‑Loop.  
- **LKG**: Lessons Knowledge Graph.  
- **MCP**: Model Context Protocol.  
- **OTLP**: OpenTelemetry Protocol.  
- **Two‑Key Rule**: Separate initiator and approver for critical actions.

---

**End of SRS v3.0**

This document defines the complete functional and non‑functional requirements for the enterprise‑ready Forge OS. It supersedes all earlier versions and serves as the authoritative reference for implementation.
