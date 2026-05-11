# Software Requirements Specification  
## Forge OS – Self‑Sustaining Software Engineering Ecosystem  
**Version 3.1 – Complete Integrated SRS**  
**Date:** 2026‑05‑10  
**Author:** Forge OS Architecture Team  

> *This document consolidates and supersedes all previous versions (v1.0, v2.0, v3.0). Every functional requirement from the original SDLC engine, the OpenClaw‑enhanced capabilities, and the enterprise‑grade security/observability additions is included. No requirement or feature has been omitted.*

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
   3.10 [Cross‑Project Global Memory](#310-cross-project-global-memory)  
   3.11 [Background Daemon & Always‑On Monitoring](#311-background-daemon--always-on-monitoring)  
   3.12 [Dreamer Agent & Passive Knowledge Consolidation](#312-dreamer-agent--passive-knowledge-consolidation)  
   3.13 [Lazy Context Builder](#313-lazy-context-builder)  
   3.14 [Channel Adapter Layer](#314-channel-adapter-layer)  
   3.15 [Layered Sandbox Security](#315-layered-sandbox-security)  
   3.16 [Extension Ecosystem](#316-extension-ecosystem)  
   3.17 [OpenClawAdapter](#317-openclawadapter)  
   3.18 [Human‑in‑the‑Loop Governance](#318-human-in-the-loop-governance)  
   3.19 [End‑to‑End Observability & Audit](#319-end-to-end-observability--audit)  
   3.20 [Token Economics & Cost Management](#320-token-economics--cost-management)  
4. [External Interface Requirements](#4-external-interface-requirements)  
   4.1 [User Interfaces](#41-user-interfaces)  
   4.2 [Hardware Interfaces](#42-hardware-interfaces)  
   4.3 [Software Interfaces](#43-software-interfaces)  
   4.4 [Communication Interfaces](#44-communication-interfaces)  
5. [Non‑Functional Requirements](#5-non-functional-requirements)  
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
Forge OS is a **standalone, self‑sustaining software engineering ecosystem** that orchestrates the complete software development lifecycle (SDLC) through a pipeline of specialized AI agents, multi‑modal quality gates, and a continuous cross‑project learning memory system. It is not a plugin for a specific IDE or a single AI model; it is a kernel‑agnostic platform that any developer or team can adopt to build, maintain, and evolve software with minimal manual process overhead.

This SRS defines the complete functional and non‑functional requirements for Forge OS Version 3.1, incorporating:
- Core SDLC pipeline orchestration (12‑stage, extensible)
- Specialized AI agents with persona‑based tool restrictions
- Multi‑modal gates with risk levels and sandboxed execution
- Three‑tier graph‑based memory (Lessons Knowledge Graph, Artifact Dependency Graph)
- Self‑learning loops (reflection, lesson extraction, skill mining, dream consolidation)
- Enterprise‑grade security: gVisor sandboxing, phase‑based access control, credential proxy
- Structured Human‑in‑the‑Loop (HITL) governance with risk‑based escalation and cryptographic signing
- Dual‑stream OpenTelemetry tracing and immutable append‑only audit ledger
- Token economics monitoring and cost attribution
- Kernel‑agnostic architecture with adapters for Claude, GPT, OpenClaw, and local models
- Gradual adoption profiles (`minimal`, `standard`, `expert`)
- Background daemon with always‑on monitoring and offline knowledge consolidation
- Community‑pluggable extension ecosystem via MCP protocol

### 1.2 Scope
The system encompasses:
- A **12‑stage SDLC pipeline** (extensible) from requirements gathering to post‑release retrospectives, with automated state transitions.
- **16 specialized agents** (12 stage agents + 4 cross‑stage) with tuned personas, tool restrictions, and scoped context.
- **Multi‑modal gate enforcement** that validates artifacts using file checks, pattern matching, external commands (sandboxed), AI reviews, and metric thresholds, each with a risk classification.
- A **three‑tier memory architecture** that remembers session context, project‑level decisions/lessons (LKG), and cross‑project global knowledge.
- **Self‑learning mechanisms**: automatic reflection, lesson extraction, skill mining, knowledge graph management, and dream consolidation.
- **Self‑testing health daemon** that monitors the system’s own integrity (hook tests, gate simulations, knowledge decay).
- **Kernel Adapter Layer** that abstracts the underlying AI provider (Claude, GPT, OpenClaw, local models, human) so the ecosystem is never vendor‑locked.
- **Background daemon** for always‑on monitoring and scheduled knowledge maintenance.
- **Channel Adapter Layer** for lightweight integration with messaging platforms (feedback intake, status queries, release broadcasting).
- **Layered sandbox security** (gVisor, credential proxy, phase‑based access control).
- **Human‑in‑the‑Loop governance** with risk‑based routing, maker‑checker enforcement, and cryptographic decision trail.
- **End‑to‑end observability** (dual‑stream tracing, immutable audit ledger, artifact lineage).
- **Token economics** (cost attribution, context relevance scoring, budget enforcement).
- **Gradual adoption profiles** that allow users to start with a minimal 3‑stage pipeline and unlock advanced features as needed.
- **Extension ecosystem** (pluggable agents, gates, kernel adapters, profile packs) via MCP.

### 1.3 Definitions, Acronyms, and Abbreviations
- **ADG**: Artifact Dependency Graph – a directed graph describing how pipeline artifacts depend on each other.
- **Audit Ledger**: An immutable append‑only log of all significant events (gate advances, HITL decisions, tool calls).
- **Capsule**: A token‑optimised context unit containing full or skeleton versions of artifacts.
- **Dreamer Agent**: An asynchronous agent that consolidates daily logs, re‑ingests old reflections, and proposes memory maintenance actions.
- **Gate**: A checkpoint of criteria that must be met before proceeding to the next stage.
- **gVisor**: A user‑space kernel that provides container isolation with a small attack surface.
- **HITL**: Human‑in‑the‑Loop – structured checkpoints where a human must approve, choose, or provide feedback.
- **Kernel**: The underlying AI execution environment (Claude, GPT, OpenClaw, local LLM, human).
- **LKG**: Lessons Knowledge Graph – a semantic graph of learned rules, their confidence, relationships, and temporal data.
- **MCP**: Model Context Protocol – a standard for connecting AI agents to external tools and memory.
- **OTLP**: OpenTelemetry Protocol – used for exporting traces, metrics, and logs.
- **Sandbox**: A restricted execution environment (gVisor container) that prevents unauthorised access.
- **SDLC**: Software Development Life Cycle.
- **SRS**: Software Requirements Specification (this document).
- **Two‑Key Rule**: A security principle requiring two separate identities for initiation and approval of critical actions.

### 1.4 References
- Forge OS Architecture Overview v3.1 (internal)
- IEEE 830‑1998 – Recommended Practice for Software Requirements Specifications
- OpenClaw Security Documentation
- OWASP Top 10 for LLM Applications
- W3C Agentic Integrity Verification Specification (draft)

### 1.5 Overview
Section 2 gives a high‑level description of the system. Section 3 enumerates all functional requirements grouped by subsystem. Section 4 specifies interfaces. Section 5 covers non‑functional requirements. Appendices provide additional reference material.

---

## 2. Overall Description

### 2.1 Product Perspective
Forge OS is a distributed, local‑first system that can operate entirely on a developer’s machine or scale to a team server. It interacts with:
- **AI kernels** through a standardised Kernel Adapter Layer.
- **External tools** (test runners, linters, security scanners) via MCP servers or sandboxed commands.
- **Human stakeholders** via CLI, web dashboard, and messaging channels (through the Channel Adapter Layer).
- **Filesystem** for all pipeline artifacts, knowledge graphs, audit logs, and configuration.
- **Version control system (Git)** optionally for artifact versioning.

It is not embedded in any existing IDE; it is a **lifecycle orchestration layer** that sits above the actual coding environment.

### 2.2 Product Functions
- Automate the entire software lifecycle from requirements to post‑release retrospectives.
- Manage a project through all 12 SDLC stages, automatically or user‑driven.
- Generate, review, and enforce quality checks on all software artifacts.
- Enforce quality gates at every stage using a mix of deterministic checks and AI review.
- Learn from user corrections, repeated patterns, and cross‑project experience to continuously improve.
- Provide full visibility into every decision, tool call, and stage transition.
- Ensure security through least‑privilege sandboxes and separation of duties.
- Allow safe delegation of high‑risk actions to humans through structured approval workflows.
- Scale from a single developer using a 3‑stage pipeline to an enterprise team with full governance.
- Continuously test its own components (health daemon) to ensure long‑term reliability.

### 2.3 User Characteristics
- **Primary user**: Software developer or engineer, any experience level.
- **Secondary user**: Technical project manager or team lead who monitors pipeline health and progress.
- **Tertiary user**: Compliance officer who audits the development process.
- **Quaternary user**: Community contributor who extends the ecosystem with new agents, stages, gates, or profiles.

The system must accommodate users who prefer minimal automation (`minimal` profile) and those who want full, autonomous orchestration (`standard` or `expert`).

### 2.4 Operating Environment
- **OS**: Linux (primary), macOS, Windows (via WSL2 for sandboxing).
- **Runtime**: Python 3.12+ with optional Node.js for some MCP servers.
- **Storage**: Local filesystem (standard profiles: SQLite, Git‑versioned artifacts); optional external Neo4j/PostgreSQL for graph memory.
- **Container Runtime**: gVisor `runsc` for sandboxed execution (optional in `minimal` profile).
- **Network**: Required only for remote AI kernels and community extensions; all core pipeline logic works offline.
- **Disk storage**: For artifacts and knowledge bases; memory usage is minimal (<1 GB idle for daemon).

### 2.5 Design and Implementation Constraints
- All persistent data must be stored in open, human‑readable formats (Markdown, YAML, JSON, GraphML) to avoid vendor lock‑in and enable Git‑based version control.
- The system must be modular: every component (agent, gate, kernel adapter, MCP server) must be replaceable via a defined interface.
- The Kernel Adapter Layer must provide a language‑agnostic interface definition.
- The system must never block indefinitely; all gate checks must have configurable timeouts and degradation strategies.
- The audit ledger must be immutable and verifiable via cryptographic HMAC chaining.

### 2.6 Assumptions and Dependencies
- The user has access to at least one AI kernel (local or remote) for agent operation.
- External tools (test runners, linters) are available in the execution environment or can be containerised.
- The filesystem is reliable for state persistence; no transactional database is required for core operation.
- The gVisor runtime is installed for sandboxed execution (in `standard` and `expert` profiles).

---

## 3. System Features (Functional Requirements)

### 3.1 Orchestration Engine & SDLC Pipeline

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OE‑001 | **Pipeline State Machine** – Maintain a 12‑stage state machine (SRS → Product → Architecture → Spec → Plan → Build → Eval → Deploy → Monitor → Feedback → Resolve → Release). State is persisted in `pipeline/state.md` and a machine‑readable JSON. | All transitions are deterministic and tracked. |
| FR‑OE‑002 | **Stage Entry Commands** – Provide a unified CLI or API to enter any stage (e.g., `forge stage start srs`). The engine verifies that the previous gate is passed before allowing entry. | Blocked if gate not met; forced override available with admin flag and audit trail entry. |
| FR‑OE‑003 | **Lifecycle Hooks** – Expose events `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd` with registered hook scripts. | Hooks run in a defined order; failures are logged and do not crash the session. |
| FR‑OE‑004 | **Async Workflow Dispatch** – When a stage requires an agent, the engine asynchronously spawns the specialized agent through the Kernel Adapter and monitors its progress. | The engine can handle multiple parallel agents if stage logic allows (e.g., Build and Eval can run on different modules). |
| FR‑OE‑005 | **Resume & Status** – Commands `forge status` and `forge resume` display current pipeline position, active agents, and next steps; resume restores full context from state and memory. | Works across sessions; context is reconstructed identically after restart. |

### 3.2 Kernel Adapter Layer

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑KA‑001 | **Adapter Interface Definition** – Define a formal interface (`IKernelAdapter`) with methods: `get_capabilities()`, `spawn_agent(persona, context, tools)`, `on_event(event)`, `sync_memory()`. | The interface is language‑agnostic and documented. |
| FR‑KA‑002 | **Capability Introspection** – Adapter reports available tools, MCP servers, agent types, and hook support. | Forge OS Capability Manager merges this with stage requirements to build a final tool allowlist. |
| FR‑KA‑003 | **Multiple Implementations** – Provide reference adapters for Claude, OpenAI, OpenClaw, local LLM (e.g., Ollama), and a “Human” adapter; the ecosystem must support loading adapters via plugins. | User can switch kernels by changing a config value; no code change in core. |
| FR‑KA‑004 | **Tool Mapping** – The adapter translates abstract tool permissions (e.g., “Read”, “Write”, “Bash”) into kernel‑specific tool calls. | Access is enforced even if the kernel supports more tools. |
| FR‑KA‑005 | **Event Translation** – The adapter receives lifecycle events in a normalized format and returns responses that the core engine understands (e.g., “additional context”, “block with exit code”). | Hooks remain kernel‑agnostic. |

### 3.3 Specialized Agent System

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑AG‑001 | **16 Pre‑defined Agents** – 12 stage agents (Requirements Analyst, Product Designer, System Architect, Spec Writer, Planner, Builder, Evaluator, DevOps, Observer, Triage, Resolver, Release Manager) and 4 cross‑stage agents (Reflector, Lesson Extractor, Skill Miner, Gate Checker). | Each agent has a defined YAML persona file with role, goal, allowed tools, allowed paths, and output contract. |
| FR‑AG‑002 | **Scoped Context Injection** – Before spawning an agent, the Context Pruner (part of Memory Subsystem) provides only the relevant artifacts and lessons based on the current stage and the ADG. | The context size is always under the configured token budget. |
| FR‑AG‑003 | **Agent‑Specific Tool Restrictions** – Agents may only use a subset of available tools (e.g., Requirements Analyst cannot execute Bash). Tool restrictions are enforced by the Orchestration Engine through the Kernel Adapter AND sandbox policy. | Builder agent cannot execute `Bash` outside sandbox; Architect cannot write to source directories. |
| FR‑AG‑004 | **Output Contract Enforcement** – Each agent must produce a defined set of artifacts; the Gate Checker validates their existence and basic correctness after the agent finishes. | A missing or empty artifact fails the stage gate. |

### 3.4 Gate Enforcement & Quality Evaluation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑GT‑001 | **Multi‑modal Gate Criteria** – Gates support criteria types: `FileExistence`, `PatternMatch`, `LLMReview`, `ExternalCommand`, `MetricThreshold`. Each criterion carries a risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). | A single stage can have criteria from all types; they are evaluated in parallel when possible. |
| FR‑GT‑002 | **Gate Check on Stage Advance** – When a user or automation attempts to advance to the next stage, the Gate Coordinator evaluates all criteria. If any fail (excluding warnings), advancement is blocked. The system provides a detailed report of which criteria passed/failed and how to fix them. | Blocked stages display unmet criteria and remediation tips. |
| FR‑GT‑003 | **In‑Session Nudging** – The PreToolUse and PostToolUse hooks may continuously check soft criteria (e.g., design token compliance) and feed back to the agent without blocking. | Agents receive notifications like “Warning: raw color detected; use --color-primary-500”. |
| FR‑GT‑004 | **Quantitative Evaluation Integration** – For `ExternalCommand` and `MetricThreshold`, the system executes real tools (e.g., `pytest`, `lighthouse`, `npm audit`) inside the gVisor sandbox and parses their output. | Test results, coverage percentages, and scores are extracted and compared against thresholds automatically. |
| FR‑GT‑005 | **Gate Criteria Versioning** – Gates are versioned alongside project profiles and can be updated based on health daemon recommendations or user edits. | Old criteria are archived; changes are logged in the audit ledger. |

### 3.5 Memory & Learning Subsystem

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ML‑001 | **Three‑Tier Memory** – Tier 1 (Session context injection), Tier 2 (Project graph store: LKG + ADG, stored in `.forge/`), Tier 3 (Global cross‑project knowledge: `~/.forge/`). | Each tier is clearly separated by scope; promotion rules govern movement between tiers. |
| FR‑ML‑002 | **Lesson Extraction** – A Lesson Extractor agent runs on `Stop` and detects user corrections, explicit “remember this” instructions, and patterns of repeated fixes. It creates structured lesson nodes in the Lessons Knowledge Graph (LKG). | Each lesson has a trigger, rule, why, confidence score, stage tags, and source. |
| FR‑ML‑003 | **Lesson Confidence & Decay** – Lessons start with base confidence (user‑confirmed = 0.9, inferred = 0.5). Confidence decays over time if the lesson is not reused; lessons below 0.3 confidence (dormant) are not injected into context. | A decay function is applied periodically (by Dreamer); user can boost or deprecate a lesson manually. |
| FR‑ML‑004 | **Reflector Agent** – After every `Stop` (or stage completion), a Reflector agent evaluates the session output against the current stage’s gate criteria, identifies gaps, and logs a reflection to the project state. | Reflection notes are stored and can be queried; they influence subsequent agent prompts. |
| FR‑ML‑005 | **Skill Mining** – A Skill Miner agent tracks repeated action sequences across multiple sessions. When a pattern appears ≥3 times, it generates a reusable skill definition (SKILL.md) and optionally an MCP server scaffold. | Approved skills become invocable via `forge skill <name>` and may be promoted to global library after cross‑project validation. |
| FR‑ML‑006 | **Knowledge Graph Maintenance** – The system must detect duplicate or contradictory lessons using LKG community detection (e.g., Leiden algorithm). | A health report highlights conflicting rules; the user can merge or retire them. |

### 3.6 Artifact Dependency Graph & Context Pruning

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ADG‑001 | **Artifact Dependency Representation** – All pipeline artifacts register explicit dependencies (e.g., `spec.md` depends on `architecture.md` and `api-contracts.md`) in a machine‑readable graph (`pipeline/dependencies.graphml`). The ADG builder extracts dependencies from pipeline artifact declarations and code analysis (Vexp‑style). | Graph includes edges like `GENERATED_FROM`, `INFLUENCES`; persisted as GraphML. |
| FR‑ADG‑002 | **Context Pruner** – Prior to injecting context for a stage, the pruner traverses the ADG from the required artifacts outward, using a spread‑activation algorithm with BM25, graph distance, recency, and lesson relevance. The pruner fills the token budget greedily, using “capsules” (skeleton context) for mid‑scored artifacts. | Deterministic and reproducible; the selected set is logged for auditing. Token budget respected; skeleton context reduces waste by >60% vs. full dump. |
| FR‑ADG‑003 | **Staleness Detection** – When an upstream artifact is modified, the ADG marks all downstream artifacts as “potentially stale”. A warning is displayed on `forge status` and can trigger a backtrack suggestion. | Staleness flags are cleared only after the downstream artifact is explicitly revisited. |

### 3.7 Backtrack & Rework Automation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑BT‑001 | **Feed‑Forward Propagation Engine** – When a late‑stage event (feedback, resolved bug) identifies a deficiency in an upstream artifact (SRS, spec, design system), the engine creates a backtrack ticket with a list of affected stages derived from the ADG. | Tickets appear in the project task board; they are actionable. |
| FR‑BT‑002 | **Rework Cascade** – The engine can generate a rework plan that revisits the upstream stage(s) in order, re‑launching the appropriate agents with the updated context and a “diff mode” (focus on changes). | The user approves the cascade before execution; after rework, gates re‑run on only the changed artifacts. |
| FR‑BT‑003 | **Minimal Rework** – The system attempts to minimise the number of re‑opened stages by analysing the scope of the change (via ADG). | Only truly affected artifacts are reprocessed; unchanged derivative artifacts are not regenerated. |

### 3.8 Health & Sustainability Daemon

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑HD‑001 | **Self‑Testing Suite** – The daemon runs hook unit tests and gate simulations against a “golden set” of artifacts to verify that all hook scripts and gate checks work correctly. | Tests run on schedule (e.g., weekly) or on `forge health check`; failures produce actionable reports. |
| FR‑HD‑002 | **Knowledge Integrity Checks** – Regularly scans the LKG for conflicts, extremely low confidence lessons, and stale references to missing artifacts. | Results are included in the health dashboard; automatic pruning can be enabled with user consent. |
| FR‑HD‑003 | **Token Budget Monitor** – Measures the actual token count of injected context per session and warns if it exceeds the configured budget. | Overages are logged; the pruner parameters can be tuned based on reports. |
| FR‑HD‑004 | **System Evolution Proposals** – After a configurable number of cycles, the daemon may propose improvements to the pipeline itself (e.g., adding a new gate, adjusting stage weights, modifying the skill library). | Proposals are presented as diffable changes to configuration files, requiring user approval. |
| FR‑HD‑005 | **Hook Latency Oversight** – Monitors hook execution time; if latency regularly exceeds thresholds, the daemon flags the hook for optimization. | Alerts are issued in the health report; hooks that fail repeatedly are automatically disabled (with notification). |

### 3.9 Gradual Onboarding & Adaptation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ON‑001 | **Profile Levels** – Provide `minimal` (3 stages: SRS → Build → Deploy), `standard` (full 12 stages), and `expert` (customisable stages) profiles. | User can select profile at init or upgrade later; profile change preserves existing artifacts. |
| FR‑ON‑002 | **Onboarding Wizard** – On `forge init`, detect project type and guide the user through a first‑cycle walkthrough with extra explanations and examples. | The wizard reduces cognitive load by hiding advanced options; it can be skipped. |
| FR‑ON‑003 | **Gradual Feature Unlock** – Advanced features (skill mining, backtrack, meta‑improvement proposals) remain dormant until the user has completed two full cycles, then a “Forge Growth” report offers to activate them. | Activation is opt‑in; the report explains benefits and expected learning curve. |
| FR‑ON‑004 | **Context‑Sensitive Help** – Every command and status message can be followed by `forge explain <topic>` to retrieve detailed, stage‑relevant documentation from the built‑in reference. | The help system draws from the current project’s state and accumulated knowledge. |

### 3.10 Cross‑Project Global Memory

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑GLOB‑001 | **Global Lesson Promotion** – When a lesson has been used with high confidence (≥0.8) in ≥3 distinct projects, it is promoted to `~/.forge/global-lessons.md` (backed by graph) and becomes available to all projects. | Promotion requires explicit user approval; the lesson is tagged with source projects. |
| FR‑GLOB‑002 | **Global Skill Library** – Skills that have been used successfully in multiple projects are moved to `~/.forge/skill-library/` and can be imported by any new project. | The library maintains versioning; skills can be updated centrally. |
| FR‑GLOB‑003 | **Project Profiles Memory** – For each project the user works on, Forge OS learns preferences (e.g., preferred stack, coding conventions) and stores them in `~/.forge/project-profiles.yaml`. These profiles are used to seed new projects and adapt stage weights. | The user can review and edit profiles. |

### 3.11 Background Daemon & Always‑On Monitoring

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑BD‑001 | **Daemon Process** – An optional `forge daemon start` command launches a background process that lives independently of any user session. | Process survives logouts and can be systemd‑managed; resumes gracefully after host reboot. |
| FR‑BD‑002 | **Always‑On Observer Agent** – When the daemon is active and the project has reached Stage 9+, an Observer agent continuously polls monitoring endpoints and triggers alerts if anomalies are detected. | Alerts appear in the CLI, in `forge status`, and optionally via channel adapters. |
| FR‑BD‑003 | **Scheduled Dream Cycle** – The daemon runs the Dreamer Agent nightly (configurable) to consolidate daily logs, re‑evaluate old reflections, and propose memory maintenance actions. | Dream cycle results are written to a morning report; destructive actions require user approval. |
| FR‑BD‑004 | **Session‑Resilience** – If the daemon or host goes down, it can resume gracefully from the last persisted state. | No data loss; Observer picks up monitoring from the last known state. |

### 3.12 Dreamer Agent & Passive Knowledge Consolidation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑DR‑001 | **Daily Digest Generation** – The Dreamer agent summarises the day’s SDLC activity (sessions, decisions, reflections) into a `pipeline/log/daily-YYYY-MM-DD.md` file. | Digest is created daily if any activity occurred. |
| FR‑DR‑002 | **REM Re‑ingestion** – Once per week, the Dreamer re‑reads old reflections and stage decisions, checking for contradictions with newer knowledge (lessons, ADG changes). | Contradictions are logged and presented as “tensions” for human review. |
| FR‑DR‑003 | **Lesson Decay Application** – The Dreamer applies the confidence decay function to all lessons, marking those below the threshold as dormant. | Dormant lessons are not injected into context; they remain in the LKG for later revival. |
| FR‑DR‑004 | **Duplicate & Conflict Detection** – Using the LKG, the Dreamer identifies semantically similar lessons or direct conflicts (via Leiden community detection). | Detection results are added to the health report; user decides to merge or retire. |

### 3.13 Lazy Context Builder

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑LCB‑001 | **Skill Menu Injection** – When an agent is spawned, only a one‑line description of each available skill is injected into the initial context, not the full instructions. | Agent’s initial context size is reduced by at least 40% compared to eager loading. |
| FR‑LCB‑002 | **On‑Demand Skill Loading** – When the agent decides to use a skill (explicitly calls it), the full skill prompt is loaded in a subsequent context update. | The update is triggered within the same session; no manual intervention needed. |
| FR‑LCB‑003 | **Lazy Lesson Loading** – Only high‑confidence (>0.7), stage‑tagged lessons are eagerly injected. Lower‑confidence lessons appear as a retrievable index the agent can ask to expand. | The agent can request “show me all lessons about GPU issues” and receive the full details. |
| FR‑LCB‑004 | **Token Budget Guard** – The Lazy Builder still enforces the absolute token budget; it will not load a skill if doing so would exceed the limit for remaining essential context. | A clear warning is logged; the agent is told it can free context by summarising previous work. |

### 3.14 Channel Adapter Layer

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑CH‑001 | **Channel Adapter Interface** – A lightweight plugin interface that translates incoming messages from chat systems into standard Forge OS `UserPromptSubmit` events. | Interface defines `on_message(text, sender)` → returns a structured Forge event. |
| FR‑CH‑002 | **Status & Feedback Intake** – A channel can be used to submit feedback items (Stage 10) or to query pipeline status with a natural‑language command. | Triage agent picks up feedback; status query returns a readable pipeline summary. |
| FR‑CH‑003 | **Release Broadcasting** – The Release Manager agent (Stage 12) can push release notes to all configured channels without user manual copy‑paste. | Broadcast uses the channel adapter’s `send_message` method. |
| FR‑CH‑004 | **Security Scope** – Channel messages can only interact with the SDLC system, not with the underlying OS. | No agent can be spawned, no file read/write, no bash execution triggered purely from a channel message unless explicitly allowed. |

### 3.15 Layered Sandbox Security

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑SEC‑001 | **Phase‑Based Access Control** – Agents are limited by their SDLC phase. Contract writers (Stages 1‑5) cannot access `Bash` or source directories; implementers (Stage 6) cannot modify upstream artifacts; validators (Stage 7) are read‑only. | Enforcement at tool‑call and filesystem level; violations blocked and logged. |
| FR‑SEC‑002 | **gVisor Kamikaze Sandbox** – All `ExternalCommand` gates and agent `Bash` calls run inside ephemeral gVisor containers with no network (unless allowlisted), dropped capabilities, and auto‑destroy after 30s. | Agent tries to `curl` external URL → blocked; container filesystem discarded. |
| FR‑SEC‑003 | **Credential Proxy** – Agent containers never hold raw secrets; a sidecar injects scoped `FORGE_SESSION_TOKEN`. | Token is short‑lived and restricted to the current stage’s resources. |
| FR‑SEC‑004 | **Four‑Layer Defense Profile** – Each agent profile defines `sandbox_runtime`, `network_policy`, `credential_scope`, and `prompt_integrity` enforcement. | Agents cannot bypass layers or escalate privileges. |
| FR‑SEC‑005 | **Untrusted Input Marking** – All user feedback and channel messages are wrapped in a metadata envelope indicating source and trust level. | Prompt integrity framework prevents injection. |
| FR‑SEC‑006 | **Human‑in‑the‑Loop Override** – For high‑risk operations (e.g., code pushing to production, deleting artifacts), the system requires explicit user confirmation even if the gate would otherwise allow it. | Override logs are audited. |

### 3.16 Extension Ecosystem

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑EXT‑001 | **Four Extension Points** – Kernel Adapters, Stage Agents, Gate Criteria Modules, Profile Packs are standardised pluggable elements. All must implement published MCP or interface schemas. | Validation tool checks compliance before installation. |
| FR‑EXT‑002 | **`forge plug` CLI** – A command to search, install, update, and remove extensions from a local or remote registry. | Installed extensions are activated after a config reload; conflicts are detected. |
| FR‑EXT‑003 | **Isolated Extension Execution** – Extensions run with the same sandbox restrictions as core agents; they cannot override the state machine or memory systems without user consent. | Permissions are declared in the extension manifest. |

### 3.17 OpenClawAdapter

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OCA‑001 | **Agent Spawning** – The adapter translates a Forge OS agent persona, tool permissions, and context into an OpenClaw agent configuration (SOUL.md, IDENTITY.md, system prompt) and starts a session via the OpenClaw Gateway API. | Agent starts within 5 seconds of request. |
| FR‑OCA‑002 | **Tool Mapping** – Forge OS tool categories (Read, Write, Bash, etc.) are mapped to OpenClaw’s tool‑use policy (Allowlist/Denylist). | Mismatches are logged; OpenClaw’s built‑in sandbox is used. |
| FR‑OCA‑003 | **Lifecycle Event Bridging** – The adapter subscribes to OpenClaw webhooks for agent completion and translates them into Forge OS `Stop` events, forwarding the agent’s output and logs. | Reflection, gate check, and lesson extraction occur inside Forge OS immediately after agent stop. |
| FR‑OCA‑004 | **Channel Reuse** – The adapter can expose OpenClaw’s existing channel connections (WhatsApp, Telegram, etc.) to Forge OS’s Channel Adapter Layer, allowing stakeholders to interact with the pipeline through those channels. | Feedback and status queries work seamlessly; no extra bot registration needed. |
| FR‑OCA‑005 | **Memory Separation** – The adapter ensures that Forge OS’s source‑of‑truth artifacts (pipeline state, LKG) are not overridden by OpenClaw’s native memory files. | After each session, the adapter syncs any valuable new insights back to the project’s `.forge/` store. |
| FR‑OCA‑006 | **Offline Fallback** – If OpenClaw is unreachable, the adapter gracefully notifies the user and the system can fall back to another kernel adapter. | No data is lost; state remains consistent. |

### 3.18 Human‑in‑the‑Loop Governance

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑HITL‑001 | **Risk‑Based Routing** – Every gate is classified LOW, MEDIUM, HIGH, CRITICAL. LOW auto‑advances; MEDIUM shows notification with 30s override; HIGH pauses pipeline for structured HITL; CRITICAL enforces Two‑Key Rule. | All routing is auditable; user can see why an action was escalated. |
| FR‑HITL‑002 | **Type‑Aware Decision Rendering** – Checkpoints can be: `phase_gate` (artifact summary + gate results), `choice` (selectable options with diff preview), `feedback` (structured multi‑question form). Every checkpoint includes “General Feedback” and “Change Approach” options. | Rendered appropriately for CLI and web. |
| FR‑HITL‑003 | **Maker‑Checker Enforcement** – Approving identity must differ from initiating agent. No agent can approve its own stage advancement. | Self‑approval attempts logged and blocked; cryptographic signing ties decisions to identities. |
| FR‑HITL‑004 | **Classifier‑Assisted Autonomy** – An optional safety classifier can pre‑screen tool calls, auto‑approving safe ones and routing ambiguous/dangerous ones to HITL. | Classifier decisions themselves auditable. |
| FR‑HITL‑005 | **Override Trail** – Every forced advance or gate override records the reason, timestamp, and identity; downstream artifacts flagged as “human‑override”. | Health Daemon re‑evaluates those gates next cycle. |

### 3.19 End‑to‑End Observability & Audit

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OBS‑001 | **Dual‑Stream Tracing** – Every session emits (a) reasoning spans (LLM calls, tool use, MCP), (b) runtime audit spans (file access, network, process execution). All correlated by `session_id` and exported via OTLP. | Dashboard shows both streams simultaneously. |
| FR‑OBS‑002 | **Immutable Audit Ledger** – `.forge/audit/ledger.jsonl` is append‑only; each entry contains a HMAC chain signature. `forge audit verify` validates integrity. | Tampering is detectable; genesis entry signed with project key. |
| FR‑OBS‑003 | **Per‑Session Transcripts** – Write‑once log of all agent reasoning steps, tool inputs/outputs, and policy decisions. 100% sampling, no gaps. | Stored in `.forge/audit/sessions/`. |
| FR‑OBS‑004 | **Artifact Lineage Tracking** – Every pipeline artifact carries YAML frontmatter with agent ID, session ID, dependencies, and version. | `forge artifact lineage <file>` shows full provenance. |
| FR‑OBS‑005 | **Token Economics Dashboard** – Metrics for token consumption, cost per stage, context relevance score, waste %. | Aggregated in Prometheus/Grafana or built‑in CLI report. |
| FR‑OBS‑006 | **Lesson & Skill Version History** – Every LKG node and skill keeps version and usage/success metrics. | Health Daemon can auto‑deprecate low‑usage or low‑success skills. |
| FR‑OBS‑007 | **Audit Query API** – `forge audit query --risk=HIGH --stage=6` returns filtered, exportable results. | Supports compliance reporting. |

### 3.20 Token Economics & Cost Management

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑TE‑001 | **Token Cost Attribution** – For each agent session, calculate token usage (prompt + completion) and translate to cost using kernel’s pricing. | Stored in audit ledger and aggregated in dashboard. |
| FR‑TE‑002 | **Context Relevance Scoring** – Measure what percentage of injected context was actually referenced by the agent. | Used to tune the Context Pruner; low score triggers optimisation. |
| FR‑TE‑003 | **Budget Enforcement** – Per‑stage and per‑session token budgets configurable; warnings at 80%, errors at 100% (session may be paused). | Prevention of runaway token usage. |

---

## 4. External Interface Requirements

### 4.1 User Interfaces
- **CLI**: Primary interface. Commands: `forge init`, `forge stage start <name>`, `forge status`, `forge resume`, `forge health`, `forge explain`, `forge daemon start`, `forge plug install`, `forge audit query`, etc. Output is plain text with optional JSON for machine consumption.
- **Web Dashboard (optional)**: Visual pipeline status, health reports, HITL queues, audit query interface.
- **Channel UI**: Through configured channel adapters (e.g., Slack, Telegram), users receive notifications and can submit commands/feedback.

### 4.2 Hardware Interfaces
None – Forge OS runs on commodity hardware; no specialized hardware is required.

### 4.3 Software Interfaces
- **Filesystem**: Read/write to `pipeline/`, `.forge/`, and `~/.forge/` directories.
- **AI Kernels**: Through the Kernel Adapter Layer (REST, gRPC, or plugin hooks).
- **MCP Servers**: Standard MCP protocol (JSON‑RPC over stdio or HTTP) for external tools.
- **OTLP Collector**: For exporting traces and metrics (optional).
- **Sandbox Runtime**: gVisor `runsc` binary.
- **VCS (Git)**: Optional for versioning pipeline artifacts.
- **Graph Database (optional)**: For large‑scale knowledge graph storage, a plugin could use SQLite/NetworkX/Neo4j, but default is flat YAML + GraphML.

### 4.4 Communication Interfaces
- Inter‑component communication within Forge OS uses an internal event bus (in‑process for single‑user, message queue for team deployment). Events are defined in a JSON schema.
- MCP client communicates with external tool servers.
- Channel adapters communicate with messaging APIs (Telegram, Slack, etc.) through the OpenClawAdapter or custom connectors.

---

## 5. Non‑Functional Requirements

### 5.1 Performance
- **NF‑P‑01**: Hook execution latency (excluding AI kernel calls) must be <200ms on average.
- **NF‑P‑02**: Session context injection must compute inside 500ms and stay under configured token budget (default 2000 tokens).
- **NF‑P‑03**: The Orchestration Engine must be able to handle 10 concurrent projects with distinct pipelines on a single machine without significant degradation.
- **NF‑P‑04**: Agent spawn time < 5 seconds (first session may include MCP server startup).
- **NF‑P‑05**: Sandbox container start < 2 seconds.

### 5.2 Reliability
- **NF‑R‑01**: Hook failures (e.g., script error) must not crash the session; errors are logged and the stage continues with a warning.
- **NF‑R‑02**: Gate checks must be idempotent – re‑running a gate on the same artifacts yields the same result.
- **NF‑R‑03**: The system must survive a crash or power loss without corrupting persistent state (state files are written atomically using a write‑to‑temp‑then‑rename strategy).

### 5.3 Availability
- **NF‑A‑01**: The core pipeline functionality must be available offline (with local AI kernels or human adapter). Online AI kernels are optional.
- **NF‑A‑02**: The Health Daemon runs on a schedule and its temporary unavailability does not affect the main pipeline.
- **NF‑A‑03**: Background Daemon and Dreamer are optional; pipeline runs without them.

### 5.4 Security
- **NF‑S‑01**: Agent tool restrictions are enforced at the orchestration level, not left to the AI kernel’s self‑control.
- **NF‑S‑02**: No agent may modify pipeline state files directly; only the Orchestration Engine writes state after checks.
- **NF‑S‑03**: All external commands executed for gate evaluation run in a sandboxed environment (gVisor) with restricted PATH, no write access to project files unless explicitly configured.
- **NF‑S‑04**: Adherence to OWASP Top 10 for LLM Applications.
- **NF‑S‑05**: Credential proxy prevents secret leakage; no raw secrets in logs.
- **NF‑S‑06**: All HITL decisions are cryptographically signed; immutable audit ledger with HMAC chain.

### 5.5 Maintainability & Extensibility
- **NF‑M‑01**: All components (agents, gates, kernel adapters, channel adapters) follow a plugin architecture with clearly defined interfaces; a contributor can add a new stage without modifying core code.
- **NF‑M‑02**: Configuration is separated into version‑controlled YAML files; the system includes a schema validator.
- **NF‑M‑03**: Every automated decision made by the system (lesson extraction, skill proposal, gate advancement) is logged in a human‑readable audit trail.

### 5.6 Portability
- **NF‑PORT‑01**: The core engine must run on any platform supporting Python 3.12+ (or equivalent JavaScript runtime if implemented in Node).
- **NF‑PORT‑02**: Kernel adapters must be replaceable without rebuilding the core; switching from Claude to a local LLM is a one‑line config change.

### 5.7 Usability
- **NF‑U‑01**: The onboarding wizard (minimal profile) must allow a new user to go from `forge init` to a completed first cycle (3 stages) in under 30 minutes of wall‑time, assuming a simple project.
- **NF‑U‑02**: All status messages and error outputs must be free of internal jargon; use plain terms like “Stage 3 Gate: Architecture document exists? (YES)”.
- **NF‑U‑03**: The user can always override or postpone any gate; the system respects the explicit command without punishment (subject to audit).

### 5.8 Observability & Audit
- **NF‑OBS‑01**: 100% of tool calls, gate evaluations, and HITL decisions are recorded in the audit ledger.
- **NF‑OBS‑02**: Traces exportable to any OTLP‑compatible backend.
- **NF‑OBS‑03**: Audit ledger verifiable offline using `forge audit verify`.
- **NF‑OBS‑04**: Per‑session transcripts retained for at least 90 days (configurable).

---

## 6. Appendix A: SDLC Stage Definitions

The standard 12 stages are as follows (custom profiles can shorten or reorder):

| Stage | Purpose | Primary Agent |
|-------|---------|----------------|
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

**Stage 6 (Build):**

| Criterion | Type | Threshold | Risk |
|-----------|------|-----------|------|
| All DAG tasks marked “Done” | FileExistence | required | LOW |
| Unit test coverage > 80% | MetricThreshold | 80% | HIGH |
| Lint passes (0 errors) | ExternalCommand | exit 0 | MEDIUM |
| No raw CSS values in UI files | PatternMatch | must pass | LOW |
| All REQ‑IDs have at least one test case | LLMReview | manual review | MEDIUM |

**Stage 8 (Deploy):**

| Criterion | Type | Threshold | Risk |
|-----------|------|-----------|------|
| Staging deploy dry‑run succeeds | ExternalCommand | exit 0 | HIGH |
| Production deploy approval | HITL | explicit approval | CRITICAL |

**Stage 7 (Eval) – additional examples:**

| Criterion | Type | Threshold | Risk |
|-----------|------|-----------|------|
| All integration tests pass | ExternalCommand | exit 0 | HIGH |
| API contract tests pass | ExternalCommand | exit 0 | HIGH |
| Lighthouse score > 90 (for full‑stack) | MetricThreshold | 90 | MEDIUM |
| Security scan reports no high‑severity issues | ExternalCommand | 0 high severity | HIGH |
| Reflector agent rates quality ≥ 7/10 | LLMReview | ≥7 | MEDIUM |

*All gate criteria are configurable per project profile and versioned in `pipeline/gates.yaml`.*

---

## 8. Appendix C: Glossary

| Term | Definition |
|------|-------------|
| **ADG** | Artifact Dependency Graph – directed graph linking pipeline artifacts. |
| **Audit Ledger** | Immutable append‑only log of all significant events with HMAC chain. |
| **Capsule** | Token‑optimised context unit containing full or skeleton versions of artifacts. |
| **Dreamer Agent** | Offline consolidation agent that applies decay, detects conflicts, and generates digests. |
| **gVisor** | User‑space kernel providing container isolation. |
| **HITL** | Human‑in‑the‑Loop – structured approval checkpoints. |
| **Kernel** | Underlying AI execution environment (Claude, GPT, OpenClaw, local LLM, human). |
| **LKG** | Lessons Knowledge Graph – graph of learned rules with confidence and relationships. |
| **MCP** | Model Context Protocol – standard for connecting AI agents to external tools. |
| **OTLP** | OpenTelemetry Protocol – used for exporting traces, metrics, and logs. |
| **Sandbox** | Restricted execution environment (gVisor container). |
| **Two‑Key Rule** | Security principle requiring two separate identities for initiation and approval of critical actions. |

---

**End of SRS v3.1 – Complete Integrated Version**

*This document defines the complete functional and non‑functional requirements for Forge OS, incorporating all features from v1.0, v2.0, and v3.0. No requirement or feature has been omitted. It serves as the authoritative specification for implementation.*
