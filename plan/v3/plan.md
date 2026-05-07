# Forge OS – End‑to‑End Construction Plan  
## Traceable, Maintainable, AI‑Assisted Build of the Self‑Sustaining SDLC Ecosystem

This plan transforms the complete specification (original SRS, OpenClaw‑inspired enhancements, sandboxing, HITL, and observability) into a step‑by‑step build programme. Every phase yields a working, testable increment; every task is sized for a small team or an AI‑coding assistant. The structure is designed for **long‑term maintainability**: modular services, clear interfaces, immutable audit, and versioned artifacts.

---

### Plan Principles (for both humans and AI tools)

- **Modular by contract** – Every component communicates via a defined interface (MCP, OpenTelemetry, CLI, or REST). Replace one piece without touching others.
- **Test‑first** – Each requirement has an automated test (unit, integration, gate simulation) written *before* the implementation.
- **Immutable audit from day one** – All decisions, tool calls, and state transitions are append‑only. No log is ever deleted.
- **Version everything** – Artifacts, lessons, skills, gates, and even the pipeline definition carry version metadata.
- **AI‑assisted friendly** – Tasks are described with clear inputs, outputs, and acceptance criteria. Dependencies are explicit. Each task is a self‑contained change set that can be reviewed independently.
- **Progressive complexity** – The system starts with a minimal, safe kernel and adds features in layers that can be enabled/disabled per project.

---

## Phase 0 – Foundation: The Minimal Viable SDLC Brain  
**Duration:** 6 weeks  
**Goal:** A local CLI that can walk a developer through a 3‑stage pipeline (SRS → Build → Deploy) with state persistence. No AI agents yet; everything is manually filled.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T0.01 | Define project structure and file schemas | File layout spec | `pipeline/`, `.forge/`, `tasks/`, config templates | `forge init` creates correct scaffolding | FR‑OE‑001 (state machine schema) |
| T0.02 | Implement pipeline state machine (read/write state) | State schema | `state-manager.py` – atomic reads/writes to `pipeline/state.md` and JSON mirror | Unit tests for transition validity; idempotent writes | FR‑OE‑001, FR‑OE‑005 |
| T0.03 | CLI skeleton with `init`, `status`, `stage` commands | Click/Typer library | `forge` CLI entry point | Manual walkthrough: init, show status, advance stage manually | FR‑OE‑002, FR‑CH‑001 (later) |
| T0.04 | 3‑stage pipeline (SRS, Build, Deploy) with stub commands | Hardcoded stage list | `/forge:srs`, `/forge:build`, `/forge:deploy` as simple CLI commands that update state | User can advance through stages without gates | FR‑OE‑002 |
| T0.05 | Basic gate system: `FileExistence` and `PatternMatch` | Gate criteria DSL | `check-gate.py` that reads gate definitions and checks artifact existence/content | Gate passes when expected files exist; fails otherwise | FR‑GT‑001, FR‑GT‑002 |
| T0.06 | `forge resume` – reads state and tells user where they left off | `state.md` | CLI output showing current stage, next action | Resume after restart shows correct stage | FR‑OE‑005 |
| **Milestone 0** | **A developer can init a project, walk SRS→Build→Deploy manually, and resume.** | | | All T0.xx tasks pass | SRS v1.0 baseline functions |

---

## Phase 1 – Core Pipeline & Lifecycle Hooks  
**Duration:** 10 weeks  
**Goal:** Introduce a full 12‑stage state machine, lifecycle hooks (SessionStart, Stop, etc.), and the capability to spawn agents through a dummy kernel adapter.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T1.01 | Define all 12 stages and valid transitions | Original SDLC definition | `pipeline/stages.yaml` – machine‑readable stage definitions with allowed next stages | State manager only permits valid transitions | FR‑OE‑001 |
| T1.02 | Implement hook event bus (in‑process) | Hook interface spec | Event dispatcher that fires `SessionStart`, `SessionEnd`, `Stop`, etc., with registered callbacks | Plug‑and‑play hook scripts; test with mock events | FR‑OE‑003 |
| T1.03 | `SessionStart` hook – load state + lessons + design system | `state.md`, `tasks/lessons.md` | Injects `<2000 token` context block into session | Test with simulated start; measure token count | FR‑ML‑001, NF‑P‑02 |
| T1.04 | `UserPromptSubmit` hook – detect stage intent and prune context | User text | `additionalContext` with stage‑specific artifacts | When user types “let’s start architecture”, hook provides relevant context | FR‑ADG‑002 (early version) |
| T1.05 | `Stop` hook – reflection (simple) and gate check dispatch | Session transcript, stage gate criteria | Writes reflection note; runs gate checker for current stage | Stop event triggers gate evaluation; results logged | FR‑ML‑004, FR‑GT‑002 |
| T1.06 | `PreToolUse` hook – design system enforcement (detect raw CSS) | File content before write | Feedback message if violation found; does not block | Agent writing `#ff0000` receives “use --color‑primary‑500” | FR‑GT‑003, FR‑AG‑003 |
| T1.07 | `SubagentStop` and `SessionEnd` hooks – capture output, finalise state | Agent output, session summary | Updates `pipeline/state.md`, writes session summary | After agent finishes, state advances | FR‑OE‑003, FR‑ML‑001 |
| T1.08 | Dummy Kernel Adapter (no AI) – accepts persona + context, returns placeholder | Persona file, context | Returns a predefined “agent output” string | Integration test: stage spawns dummy agent, hooks react | FR‑KA‑001 |
| T1.09 | Wire all 12 stage skills (`/forge:srs` … `/forge:release`) to state machine | Stage definitions | Each command triggers state transition check, loads persona, calls adapter | Walk through all 12 stages with dummy agents | FR‑OE‑002, FR‑AG‑004 |
| **Milestone 1** | **Full 12‑stage pipeline walks through with dummy agents; hooks fire correctly.** | | | Integration test suite passes | SRS v1.0 core pipeline |

---

## Phase 2 – Specialized Agents & Multi‑Modal Gates  
**Duration:** 8 weeks  
**Goal:** Replace dummy agents with real specialized personas and introduce quantitative gate evaluation (LLMReview, ExternalCommand).

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T2.01 | Write persona files for all 12 stage agents + 4 cross‑stage agents | Agent registry from SRS | `agents/*.md` with role, goal, allowed tools, output contract | Each file validates against a schema | FR‑AG‑001 |
| T2.02 | Implement Agent Spawner – loads persona, injects context, invokes Kernel Adapter | Persona file, pruned context | Configured agent sub‑process or API call | Test with Claude/OpenAI adapter (real LLM) | FR‑AG‑002 |
| T2.03 | Build Claude Kernel Adapter (real) | Claude API / Claude Code plugin hooks | Translates `spawn_agent(persona, context)` into Claude Code sub‑agent | End‑to‑end: `/forge:arch` spawns a real architect agent | FR‑KA‑001, FR‑KA‑002 |
| T2.04 | Upgrade gate system: add `LLMReview`, `ExternalCommand`, `MetricThreshold` types | Gate DSL extension | `check-gate.py` can run pytest, parse output, call LLM for review | Gate “unit tests > 80%” passes/fails based on real pytest run | FR‑GT‑001, FR‑GT‑004 |
| T2.05 | Implement Reflector agent – compares output to gate criteria after Stop | Agent output, stage gate criteria | Reflection report appended to state; quality rating | After a build stage, reflector notes unmet criteria | FR‑ML‑004 |
| T2.06 | Lesson Extractor – script that parses user corrections → structured lessons | Session transcript | YAML lesson entries with trigger/rule/why/confidence | User says “No, use fp16 on T4” → lesson created | FR‑ML‑002 |
| T2.07 | Basic lessons injection into SessionStart (flat list) | `tasks/lessons.md` | Relevant lessons tagged by stage are included in context block | New session for Stage 6 includes GPU lesson from prior session | FR‑ML‑003 (early) |
| **Milestone 2** | **Real agents perform stages; gates evaluate automatically; lessons extracted** | | | Full integration test: project SRS→Build with AI agents | SRS v1.0 learning core |

---

## Phase 3 – Memory & Intelligent Context  
**Duration:** 10 weeks  
**Goal:** Three‑tier memory fully working, Artifact Dependency Graph (ADG) built and used for context pruning, cross‑project global lessons.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T3.01 | Build Artifact Dependency Graph (ADG) engine | Pipeline artifact manifest | `adg-builder.py` – creates `dependencies.graphml` from artifact declarations | ADG auto‑updates; `forge adg show` visualises | FR‑ADG‑001 |
| T3.02 | Implement Context Pruner using ADG + stage | ADG, token budget | `context-pruner.py` – spread‑activation algorithm, selects artifacts under token limit | When entering Stage 6, only task DAG + relevant spec sections injected | FR‑ADG‑002, NF‑P‑02 |
| T3.03 | Three‑tier memory implementation: Tier‑3 global store (`~/.forge/`) | Tier‑2 project lessons | `global-lessons.md` and promotion logic (≥3 projects) | Lesson from project A appears in project B context after promotion | FR‑GLOB‑001, FR‑GLOB‑002 |
| T3.04 | Lesson Knowledge Graph (LKG) – replace flat files with graph store | Existing lessons, MCP memory server | Neo4j / Kioku‑Lite backend; `lkg‑manager.py` | Lessons are nodes with relations; query “all GPU lessons for Stage 6” returns accurate list | FR‑ML‑003, FR‑ML‑006 |
| T3.05 | Confidence decay & dormant marking | LKG, decay policy | Dream‑cycle script that reduces confidence of unused lessons; marks dormant | Lesson not used for 90 days → not injected; confidence drops | FR‑ML‑003 |
| T3.06 | Backtrack ticket generation from ADG staleness | ADG, changed upstream artifact | `backtrack‑detector.py` – flags downstream artifacts that may be stale | When `architecture.md` changes, spec and plan marked “needs review” | FR‑BT‑001 |
| T3.07 | `forge resume` enhanced – full context reconstruction from state + LKG + ADG | State, LKG, ADG | Exact context that was present at last stop is re‑injected | Resume works identically to original session | FR‑OE‑005 |
| **Milestone 3** | **Memory is graph‑based; context is pruned intelligently; cross‑project learning works.** | | | Demo: two projects share a lesson; ADG flags stale artifacts automatically | SRS v1.0 full memory |

---

## Phase 4 – Adaptive Profiles, Skill Mining & Health Daemon  
**Duration:** 8 weeks  
**Goal:** System adapts to project type, auto‑generates skills, and self‑tests.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T4.01 | Project type detection (API, fullstack, ML, CLI, library) | File structure, user input | `project-type-profiles.yaml` with stage overrides | `forge init` correctly identifies a React app as fullstack and adjusts gates | FR‑ON‑001, FR‑ON‑002 |
| T4.02 | Skill Miner – track patterns, propose skills when ≥3 occurrences | `PostToolUse` logs | `mine-skills.py` generates SKILL.md drafts | Repeated “git commit –amend” sequence → proposed skill | FR‑ML‑005 |
| T4.03 | Skill approval flow and install to `.claude/skills/` or MCP | Generated SKILL.md | CLI prompt to accept/reject; installed skill becomes invocable | `/forge:commit-amend` works after approval | FR‑ML‑005, FR‑EXT‑002 |
| T4.04 | Health Daemon – hook unit tests and gate simulations | Mock events, golden artifacts | `forge health check` runs all hook tests, reports failures | A broken hook is detected and flagged; known‑good gate always passes | FR‑HD‑001, FR‑HD‑002 |
| T4.05 | Token budget monitor + health report | Injected context sizes | Weekly report of token usage, overages, pruning efficiency | Report shows average context size per stage and alerts if budget exceeded | FR‑HD‑003 |
| **Milestone 4** | **System self‑adapts, self‑tests, and generates new skills.** | | | Full cycle on a sample project; skill mined; health check passes | SRS v1.0 complete |

---

## Phase 5 – Channel Adapters & OpenClaw Integration (v2 Enhancements)  
**Duration:** 8 weeks  
**Goal:** Integrate OpenClaw as a kernel adapter; add always‑on daemon, Dreamer agent, and channel‑based interaction.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T5.01 | Background Daemon process (`forge daemon start`) | Daemon manager | Long‑running process hosting Observer and Dreamer agents | Daemon survives logouts; restarts gracefully | FR‑BD‑001 |
| T5.02 | Always‑On Observer agent – monitor Stage 9+ endpoints | Monitoring config | Alerts on anomaly; messages injected into Triage stage | Simulated outage triggers alert and feedback item | FR‑BD‑002 |
| T5.03 | Dreamer Agent – daily digest, REM re‑ingestion, lesson decay application | Session logs, LKG | Morning report; contradiction proposals; dormant lesson marking | Nightly cycle reduces clutter and surfaces conflicts | FR‑DR‑001‑004 |
| T5.04 | Lazy Context Builder – skill menu + on‑demand full loading | Agent spawn context | Agent receives skill menu; when selected, full skill injected | Token usage for agent start drops 40%; full skill available when needed | FR‑LCB‑001‑004 |
| T5.05 | Channel Adapter Layer – abstract interface for messaging | Channel API spec | Console channel adapter (test); OpenClaw channels reuse | `/forge status` via Telegram returns pipeline state; feedback submitted via WhatsApp | FR‑CH‑001‑004 |
| T5.06 | OpenClawAdapter – implement Kernel Adapter using OpenClaw Gateway | OpenClaw API, tool mapping | Spawn agents via OpenClaw; lifecycle events bridged | End‑to‑end: run Stage 6 Build via OpenClaw; hooks fire normally | FR‑OCA‑001‑006 |
| T5.07 | Extension ecosystem – `forge plug` command, manifest validation | Plugin schema | Can install/uninstall community agents, gates, profiles | `forge plug install lighthouse-gate` adds new gate type | FR‑EXT‑001‑003 |
| **Milestone 5** | **System runs headless, learns passively, integrates OpenClaw, and is extensible.** | | | Full v2 functionality demo | SRS v2.0 complete |

---

## Phase 6 – Enterprise Hardening: Sandboxing, HITL, Observability (v3 Enhancements)  
**Duration:** 12 weeks  
**Goal:** Production‑grade security, governed human intervention, and tamper‑proof audit trail.

| Task ID | Task | Inputs | Outputs | Verification | Traceability |
|---------|------|--------|---------|--------------|--------------|
| T6.01 | gVisor sandbox integration (`kamikaze_execute`) | gVisor runtime, execution policy | All `ExternalCommand` and agent `Bash` run inside ephemeral gVisor container | Code execution cannot access host network or files; container auto‑destructs | FR‑SEC‑001‑v3 |
| T6.02 | Phase‑based access control engine | Stage permissions manifest | Enforcer that blocks tool calls outside agent’s stage allowlist | Builder agent cannot write to `pipeline/02-product-ux/` | FR‑SEC‑001‑v3 |
| T6.03 | Credential proxy sidecar for MCP servers | Token manager | Agents receive short‑lived `FORGE_SESSION_TOKEN`; no raw secrets | MCP calls authenticated with scoped tokens | FR‑SEC‑001c‑v3 |
| T6.04 | Risk‑based HITL routing classifier | Gate criteria risk levels | Classifier pre‑screens actions; LOW auto‑approve, HIGH pause pipeline | Write to design system triggers a HIGH checkpoint with structured UI | FR‑HITL‑001‑004 |
| T6.05 | Type‑aware HITL decision GUI (CLI/Web) | Decision types (`phase_gate`, `choice`, `feedback`) | Terminal‑ and channel‑rendered approvals with artifact diffs | “Approve architecture?” shows C4 diagram diff; user can accept or change approach | FR‑HITL‑002 |
| T6.06 | Maker‑Checker enforcement & cryptographic audit signing | Identity provider, HMAC | Approvals require different identity; signed entries in `audit‑ledger.jsonl` | Self‑approval blocked; log entry contains valid HMAC chain | FR‑HITL‑003, FR‑OBS‑002 |
| T6.07 | Dual‑stream OpenTelemetry tracing (reasoning + runtime) | OTel SDK, eBPF/Audit hooks | Traces correlated by `session_id`; span for every tool call, file access, network connection | Dashboard shows both “agent thought” and “what OS did” simultaneously | FR‑OBS‑001, FR‑OBS‑004 |
| T6.08 | Immutable audit ledger & session transcripts | Write‑once log, git‑based | `.forge/audit/ledger.jsonl` append‑only; per‑session transcript; HMAC chained | Tampering attempt visible in git; chain verifiable with `forge audit verify` | FR‑OBS‑002‑003 |
| T6.09 | Token economics dashboard & artifact lineage | OTel metrics, lineage metadata | Live dashboard of cost per stage, waste %, context relevance; artifact dependency stamps | Can answer “how much did Stage 3 cost last cycle?” and “which artifact is stale?” | FR‑OBS‑005‑006 |
| T6.10 | `forge audit query` API and CLI | Audit ledger, traces | `forge audit decisions --stage=6 --risk=HIGH` returns all high‑risk decisions | Compliance officer can export audit trail for a release | FR‑OBS‑007 |
| **Milestone 6** | **System meets all v3 security, governance, and observability requirements.** | | | Penetration test + compliance audit simulation | SRS v3.0 complete |

---

## Global Traceability Matrix (Requirement → Task)

| Requirement ID | Requirement Summary | Implemented in Tasks |
|----------------|---------------------|----------------------|
| FR‑OE‑001 | Pipeline state machine | T0.02, T1.01 |
| FR‑OE‑002 | Stage entry commands | T0.03, T1.09 |
| FR‑OE‑003 | Lifecycle hooks | T1.02, T1.07 |
| FR‑OE‑005 | Resume & status | T0.06, T3.07 |
| FR‑KA‑001 | Kernel Adapter interface | T1.08, T2.03 |
| FR‑AG‑001 | 12+ agents personas | T2.01 |
| FR‑GT‑001 | Multi‑modal gate types | T0.05, T2.04 |
| FR‑ML‑001‑003 | Lessons, extraction, confidence | T2.06, T3.03‑05 |
| FR‑ADG‑001‑002 | Artifact Dependency Graph & pruning | T3.01‑02 |
| FR‑BT‑001 | Backtrack tickets | T3.06 |
| FR‑HD‑001‑003 | Health daemon & token monitoring | T4.04‑05 |
| FR‑SEC‑001‑v3 | gVisor sandbox & access control | T6.01‑02 |
| FR‑HITL‑001‑004 | Risk‑based HITL & classifier | T6.04‑05 |
| FR‑OBS‑001‑007 | Observability & audit trail | T6.07‑10 |

*(Only key requirements shown; full matrix embedded in each task’s acceptance criteria.)*

---

## AI‑Assisted Development Guidelines

To ensure this plan is executable with AI coding tools (Claude Code, Cursor, Copilot Workspace, etc.):

1. **Each task is a standalone coding session** – The “Inputs” column lists exactly which files/configurations are available; the “Outputs” are the deliverable. AI agents can be given a task ID, a context dump of inputs, and a prompt to produce the output.
2. **Acceptance tests are written first** – In every task, the first commit is a test that fails until the feature is implemented. This gives the AI tool a clear target.
3. **Modular commits** – Tasks produce a series of small, atomic commits, each with a message like `[T2.04] Add LLMReview gate type`. This makes bisect and review trivial.
4. **Use MCP for tooling** – Wherever an external service is needed (Neo4j, test runner, sandbox), it is wrapped in an MCP server so the AI can interact with it like any other tool.
5. **Immutable log output** – AI tools themselves benefit from the audit trail; they can self‑diagnose by reading the last session’s transcript from `.forge/audit/sessions/`.
6. **Version bump on every change** – The Health Daemon (T4.04) and artifact lineage (T6.08) ensure that every update is traceable, making it safe for an AI to maintain the codebase long‑term.
7. **Test across kernels** – The plan includes a dummy adapter (T1.08) and a real adapter (T2.03). Always run the same gate suite against both to detect regressions.

---

## How to Start Today

1. **Clone the foundation repository** (even if empty) and `forge init` the Forge OS project *on itself* — dogfood from Phase 0.
2. **Run T0.01–T0.03** with an AI assistant: “I need a Python CLI that manages `pipeline/state.md` with these schemas. Write the state manager, the init command, and status command. Include unit tests. Use click.”
3. **As each task completes**, merge to main and let the AI tool summarise the changes into the project’s own `pipeline/06-implementation/progress.md` — the system learns about its own construction.

The entire build plan is self‑hosting: Forge OS will eventually orchestrate its own remaining construction once Phase 1 is stable, with the AI agents you are building helping to finish the system. That recursive self‑improvement is the ultimate proof of the ecosystem’s design.
