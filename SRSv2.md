Below are the updated and expanded **SRS.md** (Software Requirements Specification) and **PLAN.md** (Implementation Plan) for the self‑sustaining **Forge OS** ecosystem, now enriched with the operational strengths learned from OpenClaw – including a dedicated `OpenClawAdapter` – while staying absolutely focused on being the definitive, independent software engineering lifecycle brain.

---

# Forge OS  
Software Requirements Specification  
**Version 2.0 – OpenClaw‑Enhanced**

---

## 1. Introduction

### 1.1 Purpose
Forge OS is a **standalone, self‑sustaining software engineering ecosystem** that orchestrates the complete 12‑stage SDLC through a pipeline of specialised AI agents, multi‑modal quality gates, and a continuous cross‑project learning memory system. This SRS defines the functional and non‑functional requirements for Forge OS after absorbing key operational capabilities demonstrated by the OpenClaw runtime, including persistent background execution, lazy context loading, channel‑based collaboration, and a formal OpenClawAdapter.

### 1.2 Scope
Everything from the original SRS remains, plus the following new major subsystems:
- **Background Daemon Mode** – always‑on agents for post‑release monitoring and knowledge consolidation.
- **Dreamer Agent** – offline knowledge consolidation and lesson graph maintenance.
- **Lazy Context Builder** – just‑in‑time loading of skills and low‑confidence lessons to reduce token overhead.
- **Channel Adapter Layer** – lightweight integration with messaging platforms for stakeholder feedback and status checks.
- **OpenClawAdapter** – a concrete kernel adapter that uses the OpenClaw runtime as the agent execution substrate, while Forge OS retains full pipeline authority.
- **Layered Sandbox Security** – per‑agent execution restrictions inspired by OpenClaw’s production practices.
- **Extension Ecosystem** – community‑pluggable agents, gate modules, profiles, and kernel adapters.

### 1.3 Definitions
All previous definitions apply. New terms:

- **Background Daemon**: A long‑running Forge OS process that hosts the Observer and Dreamer agents.
- **Dreamer Agent**: An asynchronous agent that consolidates daily logs, re‑ingests old reflections, and proposes memory maintenance actions.
- **Lazy Context Builder**: A context injection mechanism that provides a skill menu and stage‑critical context first, and loads full skill instructions only when the agent chooses to use them.
- **Channel Adapter Layer**: An abstraction for human‑facing touchpoints (messaging apps, chat) that translates external messages into standardised Forge OS input events.
- **OpenClawAdapter**: An implementation of the Kernel Adapter interface that spawns and controls agents via an OpenClaw Gateway, using OpenClaw’s native persistence, tool sandboxing, and multi‑channel capabilities.

### 1.4 References
- Forge OS v1.0 SRS (original baseline)
- OpenClaw Architecture & Security documentation (public)
- IEEE 830‑1998

---

## 2. Overall Description

### 2.1 Product Perspective
Forge OS remains a standalone system that can be installed locally or on a team server. With the new Background Daemon and OpenClawAdapter it can optionally integrate with an OpenClaw runtime to gain 24/7 presence and omnichannel reach. The core orchestration engine, pipeline state machine, memory system, and quality gates continue to operate entirely independently.

### 2.2 Product Functions (Extended)
- All original pipeline, agent, gate, memory, and health functions.
- **Always‑on runtime** for post‑deployment monitoring and scheduled knowledge tasks.
- **Nightly dream cycle** that autonomously maintains the Knowledge Graph.
- **Lazy skill/lesson loading** to stay within strict token budgets.
- **Chat‑channel interaction** for feedback, status, and release broadcasting.
- **Sandboxed execution** of all agent tools, configurable per stage.
- **OpenClaw integration** as a first‑class kernel adapter, enabling reuse of OpenClaw’s agent hosting and channel infrastructure.

### 2.3 User Characteristics
Same as before; the new features primarily benefit teams and advanced solo developers who want low‑friction always‑on operation and stakeholder communication.

### 2.4 Operating Environment
- Added support for a headless daemon process that can run on a server, cloud VM, or even a Raspberry Pi.
- Network required only when using remote AI kernels or channel adapters.

### 2.5 Design and Implementation Constraints
- The Background Daemon and Dreamer Agent must be optional; the system must work identically in “session‑only” mode.
- The OpenClawAdapter shall not introduce a hard dependency on OpenClaw; it is an optional kernel adapter.
- All existing open‑format data constraints remain.

---

## 3. System Features (Functional Requirements) – Updated

All original requirements (`FR‑OE‑xxx` to `FR‑GLOB‑xxx`) are preserved and carry over. The following new requirements are added.

### 3.11 Background Daemon & Always‑On Monitoring

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑BD‑001 | **Daemon Process** – An optional `forge daemon start` command launches a background process that lives independently of any user session. | Process survives logouts and can be systemd‑managed. |
| FR‑BD‑002 | **Always‑On Observer Agent** – When the daemon is active and the project has reached Stage 9+, an Observer agent continuously polls monitoring endpoints and triggers alerts if anomalies are detected. | Alerts appear in the CLI, in `forge status`, and optionally via channel adapters. |
| FR‑BD‑003 | **Scheduled Dream Cycle** – The daemon runs the Dreamer Agent nightly (configurable) to consolidate daily logs, re‑evaluate old reflections, and propose memory maintenance actions. | Dream cycle results are written to a morning report; destructive actions require user approval. |
| FR‑BD‑004 | **Session‑Resilience** – If the daemon or host goes down, it can resume gracefully from the last persisted state. | No data loss; Observer picks up monitoring from the last known state. |

### 3.12 Dreamer Agent & Passive Knowledge Consolidation

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑DR‑001 | **Daily Digest Generation** – The Dreamer agent summarises the day’s SDLC activity (sessions, decisions, reflections) into a `pipeline/log/daily-YYYY-MM-DD.md` file. | Digest is created daily if any activity occurred. |
| FR‑DR‑002 | **REM Re‑ingestion** – Once per week, the Dreamer re‑reads old reflections and stage decisions, checking for contradictions with newer knowledge (lessons, ADG changes). | Contradictions are logged and presented as “tensions” for human review. |
| FR‑DR‑003 | **Lesson Decay Application** – The Dreamer applies the confidence decay function to all lessons, marking those below the threshold as dormant. | Dormant lessons are not injected into context; they remain in the LKG for later revival. |
| FR‑DR‑004 | **Duplicate & Conflict Detection** – Using the LKG, the Dreamer identifies semantically similar lessons or direct conflicts. | Detection results are added to the health report; user decides to merge or retire. |

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
| FR‑SEC‑001 | **Per‑Agent Tool Profiles** – Each agent gets a YAML security profile that declares allowed tools, allowed file paths (read/write/execute), and network permissions. | Profile is enforced by the Orchestration Engine before any tool call. |
| FR‑SEC‑002 | **External Command Sandboxing** – When a `ExternalCommand` gate or agent tool requires shell execution, it runs inside a configurable sandbox (Docker, OS jail, or at minimum a restricted PATH). | The sandbox cannot access `.forge/` secrets, and has no write access to the pipeline state. |
| FR‑SEC‑003 | **Human‑in‑the‑Loop Override** – For high‑risk operations (e.g., code pushing to production, deleting artifacts), the system requires explicit user confirmation even if the gate would otherwise allow it. | Override logs are audited. |
| FR‑SEC‑004 | **Security Audit Trail** – Every tool invocation, sandbox breach attempt, and permission escalation is logged with timestamps and agent identity. | Log is stored in `.forge/security‑audit.jsonl` and is read‑only for agents. |

### 3.16 Extension Ecosystem

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑EXT‑001 | **Four Extension Points** – Kernel Adapters, Stage Agents, Gate Criteria Modules, Profile Packs are standardised pluggable elements. | Each has a defined schema; community can publish via a manifest. |
| FR‑EXT‑002 | **`forge plug` CLI** – A command to search, install, update, and remove extensions from a local or remote registry. | Installed extensions are activated after a config reload; conflicts are detected. |
| FR‑EXT‑003 | **Isolated Extension Execution** – Extensions run with the same sandbox restrictions as core agents; they cannot override the state machine or memory systems without user consent. | Permissions are declared in the extension manifest. |

### 3.17 OpenClawAdapter (Kernel Adapter Implementation)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR‑OCA‑001 | **Agent Spawning** – The adapter translates a Forge OS agent persona, tool permissions, and context into an OpenClaw agent configuration (SOUL.md, IDENTITY.md, system prompt) and starts a session via the OpenClaw Gateway API. | Agent starts within 5 seconds of request. |
| FR‑OCA‑002 | **Tool Mapping** – Forge OS tool categories (Read, Write, Bash, etc.) are mapped to OpenClaw’s tool‑use policy (Allowlist/Denylist). | Mismatches are logged; OpenClaw’s built‑in sandbox is used. |
| FR‑OCA‑003 | **Lifecycle Event Bridging** – The adapter subscribes to OpenClaw webhooks for agent completion and translates them into Forge OS `Stop` events, forwarding the agent’s output and logs. | Reflection, gate check, and lesson extraction occur inside Forge OS immediately after agent stop. |
| FR‑OCA‑004 | **Channel Reuse** – The adapter can expose OpenClaw’s existing channel connections (WhatsApp, Telegram, etc.) to Forge OS’s Channel Adapter Layer, allowing stakeholders to interact with the pipeline through those channels. | Feedback and status queries work seamlessly; no extra bot registration needed. |
| FR‑OCA‑005 | **Memory Separation** – The adapter ensures that Forge OS’s source‑of‑truth artifacts (pipeline state, LKG) are not overridden by OpenClaw’s native memory files. | After each session, the adapter syncs any valuable new insights back to the project’s `.forge/` store. |
| FR‑OCA‑006 | **Offline Fallback** – If OpenClaw is unreachable, the adapter gracefully notifies the user and the system can fall back to another kernel adapter. | No data is lost; state remains consistent. |

---

## 4. External Interface Requirements (Updated)

### 4.1 User Interfaces
- **CLI** – same as before, plus `forge daemon start`, `forge dream run --now`, `forge plug install <name>`.
- **Channel Integration** – via the Channel Adapter Layer (using OpenClaw or custom connectors), users can send `@forge status` or feedback messages.
- **Web Dashboard (optional)** – now includes health reports, dream digests, and channel activity logs.

### 4.2 Software Interfaces
- **OpenClaw Gateway API** – used by the OpenClawAdapter (HTTP/WebSocket).
- **Channel APIs** – accessed through the OpenClawAdapter or custom channel adapters.

### 4.3 Communication Interfaces
- The event bus inside Forge OS now includes events from the Background Daemon and Dreamer.

---

## 5. Non‑Functional Requirements (Carried forward + new)

All previous NFRs remain. Additions:

- **NF‑D‑001** – Background Daemon must consume < 200 MB RAM idle.
- **NF‑D‑002** – Dreamer agent cycle must complete in < 10 minutes for a project with 200 lessons.
- **NF‑LCB‑001** – Lazy context load must add < 100ms overhead to agent start.
- **NF‑CH‑001** – Channel message round‑trip must be < 2 seconds for status queries.
- **NF‑SEC‑005** – Sandbox must prevent all direct filesystem writes outside the designated workspace.

---

## 6. Appendix A – SDLC Stages (unchanged)

…

## 7. Appendix B – Gate Criteria Examples (unchanged, extended with sandbox‑specific criteria)

…

---

# Forge OS – Implementation Plan  
**Version 2.0 (Enhanced)**

## 1. Vision
Deliver a fully independent, self‑sustaining SDLC ecosystem that can run headless, learn continuously, and integrate with the OpenClaw runtime as an optional but powerful execution substrate. The implementation is divided into phases that each deliver usable value.

## 2. Phases Overview

| Phase | Theme | Key Deliverables | Dependencies |
|-------|-------|------------------|--------------|
| **Phase 1** | Core SDLC Engine | Pipeline state machine, 12 stage skills, basic agents, gates (FileExistence/PatternMatch), Tier 1‑2 memory, CLI | None |
| **Phase 2** | Learning & Quality | Reflector, Lesson Extractor, Gate multi‑modal, LKG, ADG, Context Pruner, Gate Checker | Phase 1 |
| **Phase 3** | Team & Deeper Memory | Tier 3 global memory, project profiles, backlog/resume polish, basic sandbox | Phase 2 |
| **Phase 4** | Always‑On & Dreams | Background Daemon, Observer agent, Dreamer Agent, Lazy Context Builder | Phase 2 |
| **Phase 5** | Channel & Adapter Layer | Channel Adapter interface, OpenClawAdapter (with tool mapping, channel reuse, lifecycle bridging), basic CLI channel | Phase 4 (optional) |
| **Phase 6** | Ecosystem & Sustain | `forge plug` system, health daemon self‑testing, extension registry, hardening (deep sandbox, full audit trail) | Phase 5 |

## 3. Detailed Milestones & Tasks

### Phase 1: Core SDLC Engine (Status: Not started)

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T1.1 | Orchestration Engine: state machine, hook registration, event bus | L | — |
| T1.2 | CLI scaffold: `forge init`, `forge stage`, `forge status`, `forge resume` | M | T1.1 |
| T1.3 | Agent spawn interface on Kernel Adapter (dummy adapter first) | M | T1.1 |
| T1.4 | 12 stage agent persona files & basic output contracts | L | — |
| T1.5 | Gate system: FileExistence and PatternMatch checkers | M | T1.1 |
| T1.6 | Project init & scaffolding: create `pipeline/`, `tasks/`, `.forge/` | S | T1.2 |
| T1.7 | Tier 1 context injection from `pipeline/state.md` and lessons (flat list) | M | T1.1, T1.6 |
| T1.8 | Stage transition enforcement (gate block) | M | T1.5, T1.1 |
| **Milestone 1** | Complete a manual 12‑stage walkthrough on a simple project | | |

### Phase 2: Learning & Quality

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T2.1 | Reflector agent: compare output to gate criteria after Stop | L | T1.8 |
| T2.2 | Lesson Extractor: parse user corrections → structured lesson YAML | L | T1.7 |
| T2.3 | LKG (Lessons Knowledge Graph) storage & retrieval | M | T2.2 |
| T2.4 | Gate checker multi‑modal: add LLMReview & ExternalCommand support | M | T1.5, T2.1 |
| T2.5 | ADG (Artifact Dependency Graph) builder & query engine | M | T1.6 |
| T2.6 | Context Pruner using ADG + LKG (stage‑aware) | M | T2.5, T2.3 |
| T2.7 | Backtrack ticket generation from ADG staleness (manual rework) | M | T2.5 |
| **Milestone 2** | A project automatically reflects, extracts a lesson, and prunes context | | |

### Phase 3: Team & Deeper Memory

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T3.1 | Tier‑3 cross‑project global memory: `~/.forge/global-lessons.md` sync | M | T2.3 |
| T3.2 | Project profiles (API, fullstack, ML, CLI) adaptation of stages & gates | M | T2.5 |
| T3.3 | `forge resume` improvements: full session context reconstruction | S | T2.6 |
| T3.4 | Basic sandbox: path restrictions for `Write` and `Execute` | M | T1.3 |
| T3.5 | Multi‑user event bus readiness (shared repo) | L | T1.1 |
| **Milestone 3** | A lesson from project A appears in project B, profile simplifies CLI project | | |

### Phase 4: Always‑On & Dreams

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T4.1 | Background Daemon process (`forge daemon`) | M | T1.1 |
| T4.2 | Always‑on Observer agent (monitoring endpoints, cron) | M | T4.1, T1.4 (Observer persona) |
| T4.3 | Dreamer Agent: daily digest generation | M | T4.1, T2.1 |
| T4.4 | Dreamer: REM re‑ingestion and contradiction detection | L | T4.3, T2.3 |
| T4.5 | Lesson decay application (Dreamer) | S | T4.4, T2.3 |
| T4.6 | Lazy Context Builder (skill menu + on‑demand loading) | L | T2.6 |
| T4.7 | Lazy lesson loading (index + expansion prompt) | M | T2.3, T4.6 |
| **Milestone 4** | Daemon runs Observer and Dreamer cycles, agents use lazy context, token use drops 40% | | |

### Phase 5: Channel & Adapter Layer

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T5.1 | Channel Adapter Interface definition & dummy console adapter | M | — |
| T5.2 | OpenClawAdapter: spawn agent via Gateway API, tool mapping, security profile | L | T1.3, knowledge of OpenClaw API |
| T5.3 | Lifecycle bridging: OpenClaw webhooks → Forge events | M | T5.2 |
| T5.4 | Channel reuse: expose OpenClaw channels to Forge Channel Adapter | M | T5.2, T5.1 |
| T5.5 | Feedback/status intake from channel (Triage integration) | M | T5.1, T5.4 |
| T5.6 | Release broadcasting via channel | S | T5.4 |
| T5.7 | Offline fallback for OpenClawAdapter | S | T5.2 |
| **Milestone 5** | Start a Build stage via OpenClaw; stakeholder sends feedback via Telegram | | |

### Phase 6: Ecosystem & Sustain

| Task ID | Task | Effort | Dependencies |
|---------|------|--------|--------------|
| T6.1 | `forge plug` system: install, update, remove, registry | M | — |
| T6.2 | Extension manifests & schema validation | M | T6.1 |
| T6.3 | Health Daemon: self‑testing hooks, gate simulations | L | T2.4, T2.5 |
| T6.4 | Deep sandbox: Docker/OS‑level isolation for `ExternalCommand` and agent tools | L | T3.4 |
| T6.5 | Full security audit trail (`security-audit.jsonl`) | M | T6.4 |
| T6.6 | Hardening: rate‑limiting channels, input sanitisation | M | T5.1 |
| **Milestone 6** | Community can write and share a custom gate module, system self‑tests weekly | | |

## 4. Risk Register (Key Additions)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dreamer hallucinates contradictory lesson merges | Medium | Only propose merges; human must approve; dry‑run mode available |
| OpenClaw API changes break adapter | High | Maintain adapter as community extension with version pinning; fallback to next kernel |
| Background Daemon host resource exhaustion | Medium | Configurable resource limits; health daemon monitors daemon itself |
| Channel spam leads to context pollution | Low | Rate limiting and message deduplication in Channel Adapter Layer |

## 5. Timeline Estimate (Single dedicated team)

| Phase | Duration |
|-------|----------|
| Phase 1 | 3‑4 months |
| Phase 2 | 3‑4 months |
| Phase 3 | 2‑3 months |
| Phase 4 | 3‑4 months |
| Phase 5 | 3‑4 months |
| Phase 6 | 3‑4 months |
| **Total** | 18‑24 months for a fully polished v2.0 |

## 6. Conclusion
This plan delivers a self‑sustaining, open‑community SDLC ecosystem that incorporates the best of OpenClaw’s runtime strengths without ever losing its identity as the ultimate software creation methodology engine. By Phase 5, a developer can use Forge OS entirely through their messaging app, while still enjoying rigorous quality gates and a continuously improving knowledge base.
