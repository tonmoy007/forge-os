# Forge OS: A Self‑Sustaining, Adaptive Software Engineering Ecosystem

Forget the plugin. Imagine an **independent operating system for software creation** — not an IDE, not a CI/CD toolchain, not an AI wrapper — but a living, learning, and self‑improving ecosystem that any developer can adopt. Forge OS is the culmination of the abstract architecture, built to evolve, to sustain itself, and to reduce complexity rather than add to it.

---

## 1. Core Principles That Defeat Complexity

> Complexity is not the presence of many parts; it’s the absence of clarity in how they connect.  
> Forge OS solves complexity by making every relationship explicit, every process auditable, and every component replaceable.

- **Modularity by Contract** – Every component (agents, gates, evaluators, memory stores) communicates through well‑defined interfaces. They can be hot‑swapped.
- **Kernel Agnosticism** – An abstract `KernelAdapter` layer decouples the system from any specific AI provider. Claude, Codex, OSS models, even human‑only “kernels” — all plug in the same way.
- **Gradual Onboarding** – The full 12‑stage pipeline is there, but a user can start with a three‑stage “minimal viable flow” and incrementally activate more stages as needed.
- **Self‑Maintenance** – The system monitors its own health, detects stale knowledge, and proposes improvements to itself without external scripts.
- **Open by Default** – Forge OS uses open formats (YAML, JSON, Markdown, GraphML for dependencies) so no part is a black box.

---

## 2. Architectural Layers

```
┌─────────────────────────────────────────────────────────┐
│                   USER INTERFACE                         │
│  CLI, IDE extension, web dashboard, voice, or script     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                  ORCHESTRATION ENGINE                    │
│  • Session Manager (lifecycle hooks)                     │
│  • Stage State Machine (12 stages + custom)             │
│  • Workflow Dispatcher (selects & spawns agents)        │
│  • Gate Coordinator (multi-modal evaluation)            │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                 KERNEL ADAPTER LAYER                     │
│  • Kernel Interface (spawn, prompt, tool‑use, stop)     │
│  • Implementations: Claude, GPT, OpenCode, human, …     │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│               AI KERNELS (Plugins)                       │
└─────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│              MEMORY & LEARNING SUBSYSTEM                 │
│  • Tier 1 (Session) – Context window injection           │
│  • Tier 2 (Project) – Pipeline artifacts, lessons        │
│  • Tier 3 (Cross‑Project) – Global knowledge graph       │
│  • Learning Services (Reflection, Extraction, Mining)    │
│  • Knowledge Graph (lessons, dependencies, constraints)  │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│             HEALTH & SUSTAINABILITY DAEMON               │
│  • Self‑testing (hook tests, gate simulations)           │
│  • Knowledge pruning & deduplication                     │
│  • Backtrack detection & rework automation               │
│  • Performance & token budget monitoring                 │
└─────────────────────────────────────────────────────────┘
```

Everything sits on a **distributed filesystem and event bus** — no central server required for single‑user mode, but the design scales to teams via a shared repo and event log.

---

## 3. Plugging the Improvements: How Each Challenge Becomes a Feature

### 3.1 Smart Context & Dependency Graph

**Problem:** Agents receive too much irrelevant info or miss critical upstream decisions.  
**Solution:** An explicit **Artifact Dependency Graph** (ADG) stored alongside the pipeline.

- Format: `pipeline/dependencies.graphml` (or JSON)
- Each artifact (SRS, architecture, spec, task DAG, etc.) declares its prerequisites.
- The Context Pruner traverses the graph from the current stage backward, collecting only the artifacts needed to satisfy the current activity, respecting token budgets.
- When an artifact changes (e.g., architecture update), the graph flags all downstream artifacts that “may be stale,” enabling **precise backtrack triggers**.

**Implementation:**  
A `pruner` service that uses a spread‑activation algorithm: start from the stage’s required artifacts, expand one hop, rank by relevance, and stop at the token limit. Everything is deterministic; no AI hallucination involved in selecting context.

### 3.2 Lessons as a Knowledge Graph, Not a Flat List

**Problem:** Flat lesson files become noisy, contradictory, and lack structure.  
**Solution:** Transform `tasks/lessons.md` into a **Lessons Knowledge Graph** (LKG) where each lesson is a node with:

- **Confidence** (0‑1): based on user explicit confirmation, frequency, and recency.
- **Applicability Tags**: stage, project type, trigger keywords, dependency on other lessons.
- **Decay Function**: a lesson not used or verified in 6 months loses confidence gradually.
- **Conflicts**: if two lessons suggest opposite actions, the graph logs the conflict; a human (or meta‑agent) resolves it.

The LKG can answer queries like “when working on Stage 6 with T4 GPU, what are the top 3 high‑confidence lessons?” – making context injection precise.

**Implementation:**  
Use a simple graph database (e.g., SQLite with JSON extensions, or a library like `networkx` persisted in YAML). The lesson extractor now creates nodes and edges (causes, dependencies). The pruning engine queries the graph, not a flat file.

### 3.3 Multi‑Modal Quality Evaluation Gates

**Problem:** LLM‑only gate checks are blind to real correctness (tests, lint, type safety).  
**Solution:** Each gate criterion can be of type:

- **FileExistence** – “does `architecture.md` exist?”
- **PatternMatch** – “does the design system file contain no raw hex colors?”
- **LLMReview** – “does the Reflector assess the artifact as meeting quality X?”
- **ExternalCommand** – “run `pytest`, exit code 0 and coverage > 80%”
- **MetricThreshold** – “Lighthouse score > 90, bundle size < 200KB”

Gates become a **composite evaluation**. The Gate Coordinator dispatches these checks, some asynchronous, and aggregates results.

**Sustainability:**  
The health daemon tracks which gate types catch real bugs and which are just noise. It can **auto‑tune gate weights** for a project — if a gate never fails, it might be demoted to “advisory” rather than blocking.

### 3.4 Backtrack & Rework Automation

**Problem:** A bug found in production (Stage 9) should update the SRS (Stage 1) and re‑validate all downstream artifacts. This is currently implicit.  
**Solution:** A dedicated **Feed‑Forward Propagation Engine** that listens on the event bus:

- When a `Feedback` or `Resolve` stage produces a “change request” (e.g., “SRS‑001 missing edge case”), it opens a **backtrack ticket**.
- The engine uses the ADG to determine which artifacts are affected by this upstream change and creates a **rework cascade**: a list of stages that need to be re‑visited, ordered by dependency.
- The user can approve a cascade; the system then re‑launches the corresponding stage agents with the updated context and a “rework mode” flag (which focuses on diff‑based changes rather than full regeneration).

**Complexity management:**  
Rework is scary, but the ADG makes it predictable and scoped. Without ADG, backtrack is chaos; with ADG, it’s just another workflow.

### 3.5 Continuous Self‑Testing (Pipeline Health)

**Problem:** Over time, hooks break, scripts become incompatible, and no one notices until a stage fails.  
**Solution:** Forge OS includes a **Health Daemon** that runs on schedule or on every session start:

- **Hook Unit Tests**: For each hook script, a test harness feeds mock events (using the Kernel Adapter mock) and checks output, exit codes, and side effects.
- **Gate Simulation**: For each stage, run all gate criteria against a “golden set” of known‑good and known‑bad artifacts to verify that the gate checker passes/fails correctly.
- **Knowledge Integrity**: Scan the LKG for conflicts, very low confidence lessons, or lessons that reference non‑existent artifacts.
- **Token Budget Audits**: Measure actual context injection sizes and warn if they exceed the budget.

When a test fails, the Health Daemon logs a **system health issue** and can optionally notify the user or even attempt a self‑repair (by reverting recent changes or proposing a fix). This turns the pipeline from a passive artifact into an actively maintained system.

### 3.6 Formal Kernel Adapter Interface

**Problem:** Without a clear abstraction, the system is tied to one AI vendor.  
**Solution:** Define a minimal, language‑agnostic `KernelAdapter` interface:

```
interface KernelAdapter:
    def spawn_agent(persona: AgentDefinition, context: str, tools: ToolList) -> AgentHandle
    def on_event(event: LifecycleEvent, session: SessionState) -> EventResponse
    def get_default_tools() -> ToolList
```

Implementations:  
- `ClaudeCodeAdapter` (maps to the plugin hooks we already designed)  
- `OpenAIAdapter` (uses completions with tool‑calling)  
- `LocalLLMAdapter` (wraps llama.cpp or similar)  
- `HumanAdapter` (allows a user to manually play the role of an agent, for extreme debugging)

The Orchestration Engine speaks only to the adapter. This makes the ecosystem future‑proof.

### 3.7 Gradual Adaptation & Onboarding

Complexity is the enemy of adoption. To avoid overwhelming users:

- **Profile Levels**:  
  - `minimal` – only SRS → Build → Deploy (3 stages). Hooks and lessons activate but are largely invisible.  
  - `standard` – the full 12 stages but with default gates.  
  - `expert` – unlocks custom stage definitions, fine‑tuned gates, and the meta‑improvement tools.
- **Onboarding Wizard**: On first run (`forge init`), detects project type and suggests a profile. It then walks the user through the first cycle with extra explanations, and every gate pass explains *why*.
- **Gradual Unlock**: Features like skill mining and backtrack are dormant until the user has completed two full cycles, after which a “Forge Growth” report suggests activating those advanced features.
- **Documentation is Live**: Every artifact, gate, and lesson can be inspected via commands like `forge explain gate 6` or `forge lesson list`, reducing reliance on external manuals.

---

## 4. System Sustainability: The System That Takes Care of Itself

A sustainable ecosystem is one that doesn’t rot. Forge OS achieves this through **meta‑management cycles**:

- **Weekly Health Report**: Generated by the Health Daemon (section 3.5), summarizing hook test results, knowledge graph conflicts, and token budget overruns. The user can set auto‑fix policies for low‑risk issues.
- **Knowledge Lifecycle Management**:  
  - Lessons not used in 90 days are marked “dormant” and are not injected into context.  
  - If a lesson has high confidence but low usage, it might be too specific; the system suggests a review.  
  - Duplicate lessons (semantically similar) are merged with user confirmation.
- **Skill Library Curator**: The Skill Miner (which originally proposed skills) now also monitors skill usage. If a skill is never invoked or is often overridden by the user, it is flagged for retirement. This prevents skill bloat.
- **Adaptive Stage Evolution**: The pipeline configuration (`pipeline/stages.yaml`) can be versioned. After a full cycle, the system can propose changes (e.g., “Stage 7’s gate `test-coverage` passed every time but Stage 9 often caught bugs that could have been caught earlier; consider adding a static analysis gate to Stage 6”). These proposals are presented as merge requests.
- **Community & Extensions**: By defining clear extension points (custom agents, custom gates, project profiles, kernel adapters), anyone can contribute. A decentralized “Forgeforge” (like Homebrew or npm) can distribute extensions. The ecosystem grows without the core needing to change.

---

## 5. Managing Complexity: The Forge OS “Constitution”

To ensure the system never becomes a tangle, we impose strict **architectural rules**:

1. **Every component is replaceable.** If a piece can’t be swapped out, it’s not well‑defined.
2. **Data is owned, not hidden.** Artifacts are files in a repo. The knowledge graph is an open format. No proprietary databases.
3. **Decisions are recorded as ADRs (Architecture Decision Records).** Even the system’s own evolution decisions are logged in `pipeline/decisions/`, making it possible to understand why a gate or profile was introduced.
4. **Failure to a safe state.** A gate that can’t execute defaults to “warn” not “block” — never prevents progress due to a bug in the test.
5. **Human is always the final authority.** Automation never overrides an explicit user command.

---

## 6. Implementation Roadmap (Community‑Buildable)

For an independent ecosystem to materialize, a phased approach is essential.

### Phase 0: Core Spec & Adapter
- Define the formal `KernelAdapter` spec, stage schema, gate schema, and artifact dependency graph spec.
- Build a reference implementation of the Orchestration Engine (Python/Node) that can be run locally.
- Create a simple CLI (`forge`) that uses a human adapter (no AI needed initially) to validate the pipeline logic.

### Phase 1: Basic SDLC with One Kernel
- Implement the 12 stages as plain scripts or AI agents through a Claude or OpenAI adapter.
- Gate checking with file‑existence and simple pattern matching.
- Session memory (Tier 1) and project memory (Tier 2) as files.
- Gradual onboarding (minimal profile).

### Phase 2: Learning Layer & ADG
- Add the Artifact Dependency Graph.
- Implement the Lesson Extractor and reflector with simple prompts.
- Build the Lessons Knowledge Graph and pruner.
- Introduce back‑track light: manual rework cascades suggested by the system.

### Phase 3: Full Self‑Improvement
- Skill Miner, Health Daemon, and continuous testing.
- Multi‑modal gates with external command integration.
- Auto‑tuning of gate weights and lesson confidence.
- Global cross‑project memory (Tier 3).

### Phase 4: Ecosystem & Community
- Standardize extension format (custom stages, agents, profiles).
- Forgeforge package manager.
- Web dashboard for team use.

---

## 7. Final Thought: The Un‑Plugged Vision

Forge OS, as an independent ecosystem, is not a tool — it’s a shift in how software is born. It remembers so you don’t have to. It enforces quality not through discipline but through automatic checkpoints. It grows smarter with every project, not because you told it to, but because it listened.

And because it is built on open interfaces and gradual complexity, an enthusiastic user can start with a three‑stage flow on a Sunday afternoon and, years later, find themselves orchestrating a self‑improving engineering organisation — without ever feeling lost.

The missing dots are connected. The complexity is solved by clarity. And the system sustains itself because it was designed not just to build software, but to build *its own future*.
