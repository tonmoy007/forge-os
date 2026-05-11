Below is a formal **Software Requirements Specification (SRS)** for the independent **Forge OS** ecosystem, derived from the detailed architecture, sustainability plan, and agent‑based pipeline described earlier. This document follows IEEE 830 structure and covers the complete self‑sustaining engineering platform.

---

# Software Requirements Specification  
## Forge OS – Self‑Sustaining Software Engineering Ecosystem  

**Version:** 1.0  
**Date:** 2026-05-06  
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
   3.10 [Cross‑Project Global Memory](#310-cross-project-global-memory)  

4. [External Interface Requirements](#4-external-interface-requirements)  
   4.1 [User Interfaces](#41-user-interfaces)  
   4.2 [Hardware Interfaces](#42-hardware-interfaces)  
   4.3 [Software Interfaces](#43-software-interfaces)  
   4.4 [Communication Interfaces](#44-communication-interfaces)  

5. [Non‑Functional Requirements](#5-non-functional-requirements)  
   5.1 [Performance Requirements](#51-performance-requirements)  
   5.2 [Reliability](#52-reliability)  
   5.3 [Availability](#53-availability)  
   5.4 [Security](#54-security)  
   5.5 [Maintainability & Extensibility](#55-maintainability--extensibility)  
   5.6 [Portability](#56-portability)  
   5.7 [Usability](#57-usability)  

6. [Appendix A: SDLC Stage Definitions](#6-appendix-a-sdlc-stage-definitions)  
7. [Appendix B: Gate Criteria Examples](#7-appendix-b-gate-criteria-examples)  

---

## 1. Introduction

### 1.1 Purpose
Forge OS is an independent, **self‑sustaining software engineering ecosystem** that orchestrates the full software development lifecycle (SDLC) through a pipeline of specialized AI agents, automated quality gates, and a continuous learning memory system. It is not a plugin for a particular IDE or a single AI model; it is a kernel‑agnostic platform that can be adopted by any developer or team to build, maintain, and evolve software with minimal manual process overhead.

This SRS defines the functional and non‑functional requirements for Forge OS, covering its core orchestration engine, memory architecture, learning systems, and self‑maintenance capabilities.

### 1.2 Scope
The system encompasses:
- A **12‑stage SDLC pipeline** (extensible) from requirements gathering to post‑release retrospectives, with automated state transitions.
- **Specialized agents** for each stage, each with tuned personas, tool restrictions, and scoped context.
- **Multi‑modal gate enforcement** that validates artifacts using file checks, pattern matching, external commands, and AI reviews.
- A **three‑tier memory architecture** that remembers session context, project‑level decisions/lessons, and cross‑project global knowledge.
- **Self‑learning mechanisms**: automatic reflection, lesson extraction, skill mining, and knowledge graph management.
- **Self‑testing health daemon** that monitors the system’s own integrity (hook tests, gate simulations, knowledge decay).
- **Kernel Adapter Layer** that abstracts the underlying AI provider (Claude, GPT, local models, human) so the ecosystem is never vendor‑locked.
- **Gradual adoption profiles** that allow users to start with a minimal 3‑stage pipeline and unlock advanced features as needed.

### 1.3 Definitions, Acronyms, and Abbreviations
- **SDLC**: Software Development Life Cycle  
- **SRS**: Software Requirements Specification (this document)  
- **ADG**: Artifact Dependency Graph – a directed graph describing how pipeline artifacts depend on each other.  
- **LKG**: Lessons Knowledge Graph – a semantic graph of learned rules, their confidence, and relationships.  
- **Gate**: A checkpoint of criteria that must be met before proceeding to the next stage.  
- **Agent**: A specialized AI persona that performs tasks in a particular stage.  
- **Kernel**: The underlying AI/computation provider (e.g., Claude, GPT‑4, a local LLM, or a human).  
- **Feed‑Forward**: The process of updating upstream artifacts (SRS, spec, design system) based on later‑stage discoveries.  
- **Backtrack**: Revisiting an earlier stage because a downstream change invalidates or updates an upstream artifact.  

### 1.4 References
- Forge OS Architecture Overview (internal document)  
- IEEE 830‑1998 – Recommended Practice for Software Requirements Specifications  
- SDLC‑Orchestrator Plugin Design (precursor design)  

### 1.5 Overview
Section 2 gives a high‑level description of the system. Section 3 enumerates all functional requirements grouped by subsystem. Section 4 specifies interfaces. Section 5 covers non‑functional requirements. Appendices provide additional reference material.

---

## 2. Overall Description

### 2.1 Product Perspective
Forge OS is a standalone system that can be installed on a developer’s machine, a team server, or a cloud environment. It interacts with:
- A filesystem (for pipeline artifacts, state, and memory files)
- One or more AI kernels via the Kernel Adapter Layer
- External tools (compilers, test runners, linters, scanners) for gate evaluation
- Optional user interfaces: CLI, IDE integration, web dashboard

It is not embedded in any existing IDE; it is a **lifecycle orchestration layer** that sits above the actual coding environment.

### 2.2 Product Functions
- Manage a project through all 12 SDLC stages, automatically or user‑driven.
- Generate, review, and enforce quality checks on all software artifacts.
- Learn from past corrections, mistakes, and patterns to improve future cycles.
- Detect and manage the ripple effects of changes across the entire artifact chain.
- Continuously test its own components to ensure long‑term reliability.
- Scale from a single solo developer to a distributed team by sharing the pipeline state and knowledge base.

### 2.3 User Characteristics
- **Primary user**: Software developer or engineer, any experience level.
- **Secondary user**: Technical project manager or team lead who monitors pipeline health and progress.
- **Tertiary user**: Contributor who extends the ecosystem with new agents, stages, or profiles.

The system must accommodate users who prefer minimal automation (3‑stage) and those who want full, autonomous orchestration.

### 2.4 Operating Environment
- OS: Linux, macOS, Windows (via Python runtime compatibility).
- Python 3.11+ (or equivalent runtime for the orchestration engine).
- Disk storage for artifacts and knowledge bases; memory usage is minimal (<1 GB).
- Network connectivity optional but recommended for AI kernel access and community updates.

### 2.5 Design and Implementation Constraints
- All persistent data MUST be stored in open, human‑readable formats (Markdown, YAML, JSON, GraphML) to avoid vendor lock‑in.
- The system MUST be implementable in a modular fashion where any component (agent, gate, kernel adapter) can be replaced without affecting the rest.
- The Kernel Adapter Layer MUST provide a language‑agnostic interface definition.
- The system must never block indefinitely; all gate checks must have configurable timeouts and degradation strategies.

### 2.6 Assumptions and Dependencies
- The user has access to at least one AI kernel (local or remote) for agent operation.
- External tools (test runners, linters) are available on the system path for quantitative gates.
- The filesystem is reliable for state persistence; no transactional database is required.

---

## 3. System Features (Functional Requirements)

### 3.1 Orchestration Engine & SDLC Pipeline

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OE‑001 | **Pipeline State Machine** – Maintain a 12‑stage state machine (SRS → Product → Architecture → Spec → Plan → Build → Eval → Deploy → Monitor → Feedback → Resolve → Release). State is persisted in `pipeline/state.md` and a machine‑readable JSON. | All transitions are deterministic and tracked. |
| FR‑OE‑002 | **Stage Entry Commands** – Provide a unified CLI or API to enter any stage (e.g., `forge stage start srs`). The engine verifies that the previous gate is passed before allowing entry. | Blocked if gate not met; forced override available with admin flag. |
| FR‑OE‑003 | **Lifecycle Hooks** – Expose events `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SubagentStop`, `SessionEnd` with registered hook scripts. | Hooks run in a defined order; failures are logged and do not crash the session. |
| FR‑OE‑004 | **Async Workflow Dispatch** – When a stage requires an agent, the engine asynchronously spawns the specialized agent through the Kernel Adapter and monitors its progress. | The engine can handle multiple parallel agents if stage logic allows (e.g., Build and Eval can run on different modules). |
| FR‑OE‑005 | **Resume & Status** – Commands `forge status` and `forge resume` display current pipeline position, active agents, and next steps; resume restores full context from state and memory. | Works across sessions; context is reconstructed identically. |

### 3.2 Kernel Adapter Layer

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑KA‑001 | **Adapter Interface Definition** – Define a formal interface (`IKernelAdapter`) with methods: `spawn_agent(persona, context, tools)`, `handle_event(event)`, `get_default_tools()`. | The interface is language‑agnostic and documented. |
| FR‑KA‑002 | **Multiple Implementations** – Provide reference adapters for Claude, OpenAI, and a “Human” adapter; the ecosystem must support loading adapters via plugins. | User can switch kernels by changing a config value; no code change in core. |
| FR‑KA‑003 | **Tool Mapping** – The adapter translates abstract tool permissions (e.g., “Read”, “Write”, “Bash”) into kernel‑specific tool calls. | Access is enforced even if the kernel supports more tools. |
| FR‑KA‑004 | **Event Translation** – The adapter receives lifecycle events in a normalized format and returns responses that the core engine understands (e.g., “additional context”, “block with exit code”). | Hooks remain kernel‑agnostic. |

### 3.3 Specialized Agent System

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑AG‑001 | **16 Pre‑defined Agents** – 12 stage agents (Requirements Analyst, Product Designer, System Architect, Spec Writer, Planner, Builder, Evaluator, DevOps, Observer, Triage, Resolver, Release Manager) and 4 cross‑stage agents (Reflector, Lesson Extractor, Skill Miner, Gate Checker). | Each agent has a defined persona file with role, goal, allowed tools, and output contract. |
| FR‑AG‑002 | **Scoped Context Injection** – Before spawning an agent, the Context Pruner (part of Memory Subsystem) provides only the relevant artifacts and lessons based on the current stage and the ADG. | The context size is always under the configured token budget. |
| FR‑AG‑003 | **Agent‑Specific Tools** – Agents may only use a subset of available tools (e.g., Requirements Analyst cannot execute Bash). | Tool restrictions are enforced by the Orchestration Engine through the Kernel Adapter. |
| FR‑AG‑004 | **Output Contract Enforcement** – Each agent must produce a defined set of artifacts; the Gate Checker validates their existence and basic correctness after the agent finishes. | A missing or empty artifact fails the stage gate. |

### 3.4 Gate Enforcement & Quality Evaluation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑GT‑001 | **Multi‑modal Gate Criteria** – Gates support criteria types: `FileExistence`, `PatternMatch`, `LLMReview`, `ExternalCommand`, `MetricThreshold`. | A single stage can have criteria from all types; they are evaluated in parallel when possible. |
| FR‑GT‑002 | **Gate Check on Stage Advance** – When a user or automation attempts to advance to the next stage, the Gate Coordinator evaluates all criteria. If any fail (excluding warnings), advancement is blocked. | The system provides a detailed report of which criteria passed/failed and how to fix them. |
| FR‑GT‑003 | **In‑Session Nudging** – The PreToolUse and PostToolUse hooks may continuously check soft criteria (e.g., design token compliance) and feed back to the agent without blocking. | Agents receive notifications like “Warning: raw color detected; use --color-primary-500”. |
| FR‑GT‑004 | **Quantitative Evaluation Integration** – For `ExternalCommand` and `MetricThreshold`, the system executes real tools (e.g., `pytest`, `lighthouse`, `npm audit`) and parses their output. | Test results, coverage percentages, and scores are extracted and compared against thresholds automatically. |
| FR‑GT‑005 | **Gate Criteria Versioning** – Gates are versioned alongside project profiles and can be updated based on health daemon recommendations or user edits. | Old criteria are archived; changes are logged. |

### 3.5 Memory & Learning Subsystem

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ML‑001 | **Three‑Tier Memory** – Tier 1 (Session context injection), Tier 2 (Project files: pipeline state, lessons, decisions), Tier 3 (Global cross‑project knowledge: `~/.forge/`). | Each tier is clearly separated by scope; promotion rules govern movement between tiers. |
| FR‑ML‑002 | **Lesson Extraction** – A Lesson Extractor agent runs on `Stop` and detects user corrections, explicit “remember this” instructions, and patterns of repeated fixes. It creates structured lesson nodes in the Lessons Knowledge Graph. | Each lesson has a trigger, rule, why, confidence score, and applicability tags. |
| FR‑ML‑003 | **Lesson Confidence & Decay** – Lessons start with base confidence (user‑confirmed = 0.9, inferred = 0.5). Confidence decays over time if the lesson is not reused; lessons below 0.3 confidence are not injected into context. | A decay function is applied periodically; user can boost or deprecate a lesson manually. |
| FR‑ML‑004 | **Reflector Agent** – After every `Stop` (or stage completion), a Reflector agent evaluates the session output against the current stage’s gate criteria, identifies gaps, and logs a reflection to the project state. | Reflection notes are stored and can be queried; they influence subsequent agent prompts. |
| FR‑ML‑005 | **Skill Mining** – A Skill Miner agent tracks repeated action sequences across multiple sessions. When a pattern appears ≥3 times, it generates a reusable skill definition (SKILL.md) and proposes it to the user. | Approved skills become invocable via `forge skill <name>` and may be promoted to global library after cross‑project validation. |
| FR‑ML‑006 | **Knowledge Graph Maintenance** – The system must detect duplicate or contradictory lessons, and present them for human resolution. | A health report highlights conflicting rules; the user can merge or retire them. |

### 3.6 Artifact Dependency Graph & Context Pruning

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑ADG‑001 | **Artifact Dependency Representation** – All pipeline artifacts register explicit dependencies (e.g., `spec.md` depends on `architecture.md` and `api-contracts.md`) in a machine‑readable graph (`pipeline/dependencies.graphml`). | The graph is automatically updated when new artifacts are created or dependencies change. |
| FR‑ADG‑002 | **Context Pruner** – Prior to injecting context for a stage, the pruner traverses the ADG from the required artifacts outward, using a spread‑activation algorithm, and selects the highest‑relevance artifacts until the token budget is reached. | Deterministic and reproducible; the selected set is logged for auditing. |
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
| FR‑GLOB‑001 | **Global Lesson Promotion** – When a lesson has been used with high confidence in ≥3 distinct projects, it is promoted to `~/.forge/global-lessons.md` and becomes available to all projects. | Promotion requires explicit user approval; the lesson is tagged with source projects. |
| FR‑GLOB‑002 | **Global Skill Library** – Skills that have been used successfully in multiple projects are moved to `~/.forge/skill-library/` and can be imported by any new project. | The library maintains versioning; skills can be updated centrally. |
| FR‑GLOB‑003 | **Project Profiles Memory** – For each project the user works on, Forge OS learns preferences (e.g., preferred stack, coding conventions) and stores them in `~/.forge/project-profiles.yaml`. These profiles are used to seed new projects and adapt stage weights. | The user can review and edit profiles. |

---

## 4. External Interface Requirements

### 4.1 User Interfaces
- **CLI**: Primary interface. Commands: `forge init`, `forge stage start <name>`, `forge status`, `forge resume`, `forge health`, `forge explain`, etc. Output is plain text with optional JSON for machine consumption.
- **IDE Integration**: Optional plugin that provides a visual pipeline status bar, in‑editor gate feedback, and quick‑launch of agents. Communicates with the core engine via API.
- **Web Dashboard**: Optional read‑only view of pipeline progress, health reports, and knowledge graphs, useful for teams.

### 4.2 Hardware Interfaces
None – Forge OS runs on commodity hardware; no specialized hardware is required.

### 4.3 Software Interfaces
- **Filesystem**: Read/write to `pipeline/`, `.forge/`, and `~/.forge/` directories.
- **AI Kernels**: Through the Kernel Adapter Layer (network or local process).
- **External Tools**: Invokes executables (pytest, eslint, lighthouse cli, etc.) as subprocesses for gate evaluation.
- **Graph Database (optional)**: For large‑scale knowledge graph storage, a plugin could use SQLite/NetworkX, but default is flat YAML.

### 4.4 Communication Interfaces
- Inter‑component communication within Forge OS uses an internal event bus (in‑process for single‑user, message queue for team deployment). Events are defined in a JSON schema.

---

## 5. Non‑Functional Requirements

### 5.1 Performance Requirements
- **NF‑P‑01**: Hook execution latency (excluding AI kernel calls) must be <200ms on average.
- **NF‑P‑02**: Session context injection must compute inside 500ms and stay under 2000 tokens.
- **NF‑P‑03**: The Orchestration Engine must be able to handle 10 concurrent projects with distinct pipelines on a single machine without significant degradation.

### 5.2 Reliability
- **NF‑R‑01**: Hook failures (e.g., script error) must not crash the session; errors are logged and the stage continues with a warning.
- **NF‑R‑02**: Gate checks must be idempotent – re‑running a gate on the same artifacts yields the same result.
- **NF‑R‑03**: The system must survive a crash or power loss without corrupting persistent state (state files are written atomically using a write‑to‑temp‑then‑rename strategy).

### 5.3 Availability
- **NF‑A‑01**: The core pipeline functionality must be available offline (with local AI kernels or human adapter). Online AI kernels are optional.
- **NF‑A‑02**: The Health Daemon runs on a schedule and its temporary unavailability does not affect the main pipeline.

### 5.4 Security
- **NF‑S‑01**: Agent tool restrictions are enforced at the orchestration level, not left to the AI kernel’s self‑control.
- **NF‑S‑02**: No agent may modify pipeline state files directly; only the Orchestration Engine writes state after checks.
- **NF‑S‑03**: All external commands executed for gate evaluation run in a sandboxed environment (e.g., with restricted PATH and no write access to project files) unless explicitly configured otherwise.

### 5.5 Maintainability & Extensibility
- **NF‑M‑01**: All components (agents, gates, kernel adapters) follow a plugin architecture with clearly defined interfaces; a contributor can add a new stage without modifying core code.
- **NF‑M‑02**: Configuration is separated into version‑controlled YAML files; the system includes a schema validator.
- **NF‑M‑03**: Every automated decision made by the system (lesson extraction, skill proposal, gate advancement) is logged in a human‑readable audit trail.

### 5.6 Portability
- **NF‑PORT‑01**: The core engine must run on any platform supporting Python 3.11+ (or equivalent JavaScript runtime if implemented in Node).
- **NF‑PORT‑02**: Kernel adapters must be replaceable without rebuilding the core; switching from Claude to a local LLM is a one‑line config change.

### 5.7 Usability
- **NF‑U‑01**: The onboarding wizard (minimal profile) must allow a new user to go from `forge init` to a completed first cycle (3 stages) in under 30 minutes of wall‑time, assuming a simple project.
- **NF‑U‑02**: All status messages and error outputs must be free of internal jargon; use plain terms like “Stage 3 Gate: Architecture document exists? (YES)”
- **NF‑U‑03**: The user can always override or postpone any gate; the system respects the explicit command without punishment.

---

## 6. Appendix A: SDLC Stage Definitions

The standard 12 stages are as follows (custom profiles can shorten or reorder):

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

**Stage 6 (Build):**
- All DAG tasks marked “Done”
- Unit test coverage > 80%
- Lint passes (0 errors)
- No raw CSS values in UI files (design system enforcement)
- All REQ‑IDs have at least one test case

**Stage 7 (Eval):**
- All integration tests pass
- API contract tests pass
- Lighthouse score > 90 (for full‑stack)
- Security scan reports no high‑severity issues
- Reflector agent rates quality ≥ 7/10

*These criteria are configurable per project profile.*

---

**End of SRS**

This specification provides a complete, actionable blueprint for building the self‑sustaining Forge OS ecosystem. It captures every major functional area from pipeline orchestration to health self‑maintenance, while maintaining the openness and adaptability required for widespread adoption.



**Version 1 Implementation Plan** 
for the original Forge OS ecosystem – the full standalone SDLC engine with specialized agents, multi‑modal gates, 3‑tier memory, auto‑reflection, and health daemon

---

# Forge OS – Version 1 Implementation Plan

## 1. Overview

**Goal:** Deliver a complete, self‑sustaining SDLC ecosystem that any developer can install locally and use to drive a software project from idea to post‑release learning.  
**Scope:** Originally designed 12‑stage pipeline, 16 specialized agents, hook‑based lifecycle, three‑tier memory, adaptive project profiles, skill mining, and self‑testing health daemon.  
**Reference:** SRS v1.0.

The plan is incremental; each phase produces running, testable functionality.

---

## 2. Phases

| Phase | Theme | Key Deliverables |
|-------|-------|------------------|
| 0 | Foundation | Core state machine, CLI, pipeline scaffolding |
| 1 | Pipeline & Hooks | 12 stage commands, lifecycle hooks, basic agent dispatch |
| 2 | Agents & Gates | Full agent personas, multi‑modal gate criteria, gate checker |
| 3 | Memory & Lessons | Three‑tier memory, lesson extraction, context pruning, ADG |
| 4 | Adaptive & Skills | Project profiles, adaptive workflow, skill miner |
| 5 | Health & Polish | Health daemon, self‑testing, documentation, packaging |

---

## 3. Detailed Tasks & Milestones

### Phase 0: Foundation

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T0.01 | Define pipeline state schema (`pipeline/state.md` + JSON mirror) | S | — |
| T0.02 | Build `state-manager.py` – read/write pipeline state atomically | M | T0.01 |
| T0.03 | CLI skeleton (`forge` command) with `init`, `status`, `help` | M | — |
| T0.04 | `forge init` – detect project type, scaffold directories, populate templates | M | T0.03, T0.02 |
| T0.05 | Hook event bus (internal) dispatching `SessionStart`, `Stop`, etc. | M | — |
| **Milestone 0** | CLI can init a project, show empty pipeline status | | |

---

### Phase 1: Pipeline & Hooks

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T1.01 | Stage state machine – 12 stages, valid transitions, gate‑block logic | L | T0.02 |
| T1.02 | `/forge:srs` … `/forge:release` – one slash command per stage (stub skills) | L | T1.01 |
| T1.03 | `SessionStart` hook (`session-start.py`) – load state + lessons + inject context | M | T0.05, T0.02 |
| T1.04 | `UserPromptSubmit` hook (`prompt-submit.py`) – stage detection, correction flag | M | T0.05, T1.01 |
| T1.05 | `Stop` hook (`stop-reflect.py`) – dispatch reflector, gate check (simple first) | M | T0.05 |
| T1.06 | `PreToolUse` hook for design‑system enforcement (raw value detection) | S | T0.05 |
| T1.07 | `PostToolUse` hook – decision logging to `.forge/session-log.jsonl` | S | T0.05 |
| T1.08 | `SubagentStop` hook – capture agent output, update state | S | T0.05 |
| T1.09 | `SessionEnd` hook – final persist + summary | S | T0.02, T0.05 |
| T1.10 | Wire all hooks into plugin/event config | M | T1.03‑T1.09 |
| **Milestone 1** | Pipeline loops: `/forge:srs` → agent (dummy) → `Stop` runs hooks | | |

---

### Phase 2: Specialized Agents & Gate Enforcement

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T2.01 | Write 12 stage agent personas (Markdown) with role, goal, tool permissions | L | — |
| T2.02 | Write 4 cross‑stage agent personas (Reflector, Lesson Extractor, Skill Miner, Gate Checker) | M | — |
| T2.03 | Agent spawner: load persona, inject context, restrict tools via Kernel Adapter (dummy first) | M | T2.01, T1.01 |
| T2.04 | Stage skills link personas to slash commands – each skill loads its agent | L | T2.01, T1.02 |
| T2.05 | Gate criteria definitions (`gate-criteria.md`) – machine‑readable for all stages | M | — |
| T2.06 | Gate Checker agent – evaluate criteria: `FileExistence`, `PatternMatch` | M | T2.05 |
| T2.07 | `check-gate.py` script – programmatic evaluation of gates (returns pass/fail JSON) | M | T2.06 |
| T2.08 | Gate enforcement on stage advance – block if unmet (exit code 2 on “done”) | M | T1.01, T2.07 |
| T2.09 | Reflector agent implementation – compare output to gates, log reflection | M | T2.02, T2.06 |
| **Milestone 2** | Each stage spawns its specialized agent; advance only when gates pass | | |

---

### Phase 3: Memory & Learning Subsystem

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T3.01 | Tier‑2 project memory: `tasks/lessons.md`, `.forge/lessons.yaml` sync | M | — |
| T3.02 | Lesson Extractor – detect corrections → structured lesson (Trigger/Rule/Why/YAML) | L | T2.02, T3.01 |
| T3.03 | SessionStart context injection enhanced with active lessons (<500 tokens) | M | T1.03, T3.01 |
| T3.04 | Tier‑1 context pruning – stage‑based selection of artifacts | M | T1.03 |
| T3.05 | Artifact Dependency Graph (ADG) construction from pipeline manifest | M | T0.04 |
| T3.06 | Context Pruner using ADG – spread‑activation, token budget | L | T3.05, T3.04 |
| T3.07 | Tier‑3 global memory: `~/.forge/global-lessons.md`, project profiles skeleton | M | T3.01 |
| T3.08 | Lesson promotion logic – if used in ≥3 projects → global | M | T3.07, T3.02 |
| T3.09 | `forge resume` – rebuild full session context from state + memory | M | T3.06, T0.02 |
| **Milestone 3** | Lessons flow from correction to session injection; context pruned by ADG | | |

---

### Phase 4: Adaptive Workflow & Skill Mining

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T4.01 | Project type detection logic in `forge init` (API, fullstack, ML, CLI, library) | M | T0.04 |
| T4.02 | Project profiles reference (`project-type-profiles.md`) – stage overrides, custom gates | M | — |
| T4.03 | Wire profiles into stage skills and gate checker – adjust instructions and criteria | M | T2.04, T2.06, T4.02 |
| T4.04 | Pattern tracker in `PostToolUse` – log sequence patterns to `.forge/patterns.jsonl` | M | T1.07 |
| T4.05 | Skill Miner agent – analyse patterns, propose skills when ≥3 occurrences | L | T2.02, T4.04 |
| T4.06 | Skill approval flow – generate `SKILL.md`, present to user, install on accept | M | T4.05 |
| T4.07 | Auto‑skill integration – approved skills become invocable commands | M | T4.06 |
| **Milestone 4** | New project auto‑adapts; repeated patterns become reusable skills | | |

---

### Phase 5: Health Daemon, Self‑Testing & Polish

| ID | Task | Effort | Depends On |
|----|------|--------|------------|
| T5.01 | Health Daemon – scheduled hook unit tests (mock events) | L | T0.05 |
| T5.02 | Gate simulations – run against known‑good/bad artifacts, verify pas/fail | M | T2.07 |
| T5.03 | Knowledge integrity scanner – check for lesson conflicts, stale references | M | T3.01, T3.05 |
| T5.04 | Token budget monitor – measure injected context sizes, warn if over | S | T3.06 |
| T5.05 | Comprehensive documentation – README, agent authoring guide, quickstart | L | — |
| T5.06 | End‑to‑end test – full pipeline on a sample project (TODO API) | L | All |
| T5.07 | Package & distribution – `forge` installer, PyPI/npm publishing | M | T5.06 |
| **Milestone 5** | System self‑tests weekly; ready for community adoption | | |

---

## 4. Critical Path

```
Foundation (T0.01→T0.02) → State Machine (T1.01) → Agents (T2.01→T2.03) → Gates (T2.05→T2.07)
  → Hooks (T1.03→T1.05) → Context & ADG (T3.05→T3.06) → Memory (T3.01→T3.02)
  → Adaptive (T4.01→T4.03) → Skills (T4.04→T4.06) → Health (T5.01→T5.04) → E2E (T5.06)
```

## 5. Timeline (Estimated)

| Phase | Duration |
|-------|----------|
| Phase 0 | 1 month |
| Phase 1 | 3 months |
| Phase 2 | 3 months |
| Phase 3 | 3 months |
| Phase 4 | 2 months |
| Phase 5 | 2 months |
| **Total** | **~14 months** for a full v1.0 release. |

## 6. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Hook latency > budget | Profile scripts early; use async for non‑critical hooks. |
| Context injection exceeds 2000 tokens | Aggressive pruning tuned with ADG; measure continuously. |
| Lesson extraction hallucinates rules | User confirmation; conservative thresholds; manual review queue. |
| Skill miner suggests junk | Frequency ≥3 + user approval + reject‑list. |
| Plugin conflicts with user environment | Namespace all hooks (`forge-`); document hook precedence. |
| AI kernel API changes | Kernel Adapter abstract interface isolates core; update adapters independently. |

---

**Version 1 meets the original vision: a complete, learning‑capable, quality‑enforcing SDLC operating system that any developer can run locally. It lays the foundation for the OpenClaw‑enhanced v2.0 while already being a game‑changer in software engineering automation.**
