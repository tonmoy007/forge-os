# Forge — Related Projects Map

> A landscape map of projects that solve part of what Forge solves. Organized by
> Forge's architectural layers (SRS / plugin scope) so you can quickly find prior
> art for each component you're building.
>
> Each entry has three sections:
> - **What it is** — one-line summary
> - **Borrow from it** — patterns, design choices, or code worth studying
> - **Avoid / lessons** — mistakes they made or trade-offs that bit them
>
> Last refreshed: May 2026.

---

## How to use this map

When you're about to start a task, find the layer it touches and skim the 2–3
nearest neighbours before writing anything. The goal isn't to copy — it's to
make sure you're not re-discovering an already-known failure mode.

Forge layers ↔ projects to consult:

| Forge layer | Closest prior art |
|---|---|
| 12-stage pipeline (`pipeline/01-srs` → `12-release`) | Spec Kit, Kiro, BMAD, OpenSpec, claude-sdlc |
| Hooks (`session-start`, `stop-reflect`, etc.) | claude-code-workflow-orchestration, CC Mirror |
| 16 agents (12 stage + 4 cross-stage) | great_cto, closedloop-ai/claude-plugins, CrewAI |
| Three-tier memory (session → project → `~/.forge/`) | MemGPT/Letta, Mem0, Hindsight, Reflexion |
| Reflector + Lesson Extractor | Reflexion, ExpeL, bswen reflection guide |
| Skill Miner + Gate Checker | Microsoft Agent Governance Toolkit, OPA patterns |
| `state.md` event log / replay | L0, Exarchos, agentic-sdlc |
| Adaptive workflows / profiles | BMAD Party Mode, OpenCognit CEO orchestrator |

---

## Layer 1 — Direct peers: Claude Code SDLC plugins

These are the closest neighbours. Every one of them has chosen a different path
through the same design space Forge is walking. Read their READMEs before
locking in design decisions.

### 1.1 `closedloop-ai/claude-plugins`

- **What it is.** Open-source Claude Code plugins for multi-agent software
  delivery. Plan-first SDLC workflow, code review, LLM quality judges, and
  self-learning. Bootstrap → Plan → Ship loop.
- **Borrow from it.** The "judge" pattern (LLM-as-quality-grader before merge),
  the `/bootstrap:start` → `/plan` → `/ship` slash command shape, and the
  "artifact-bound phased workflow gates that loop until correct" idea. This
  loop-until-pass is what your gate-checker should do, not just a one-shot check.
- **Avoid / lessons.** Their claim of "outperforms Opus 4.6 at half the cost"
  comes from spec-first discipline, not the plugin itself — keep your README
  honest about where the wins actually come from. Don't promise multi-repository
  support in v0.1; they built it but it's the source of most of their
  configuration complexity.

### 1.2 `danielscholl/claude-sdlc`

- **What it is.** A *marketplace* of plugins: `sdlc`, `gt-sdlc`, `skilltest`,
  `copilot`, `cadre`, plus document generators. 13 slash commands, 3
  specialized agents, GitHub/GitLab webhook watchers, all Sonnet-based for cost.
- **Borrow from it.** The marketplace pattern (`/plugin marketplace add …`) and
  the **four-layer test framework** in their `skilltest` plugin — L1-L4 tests
  validating that skill descriptions trigger correctly. This is exactly the kind
  of test infrastructure Forge will need once you have 16 skills, or you'll
  ship skills that never fire.
- **Avoid / lessons.** They split functionality across many small plugins. That's
  great for modularity but means users need to install 5+ plugins to get the
  full workflow. Forge's single-plugin approach is simpler for v0.1; resist the
  urge to split until users ask for it.

### 1.3 `great_cto` (avelikiy)

- **What it is.** Claude Code plugin with 7 specialized subagents (tech-lead,
  senior-dev, qa-engineer, security-officer, devops, l3-support,
  project-auditor) orchestrating a full SDLC: architecture → TDD → 12-angle code
  review → QA → security audit → deploy. 11 project archetypes auto-detected.
  13 compliance frameworks (GDPR, PCI-DSS, HIPAA, SOC2, ISO 27001).
- **Borrow from it.** The **archetype detection** idea — auto-detecting "this
  is a Django REST API" vs "this is a Next.js dashboard" and adapting the
  workflow. Your `.forge/profiles/` is the equivalent slot; their archetype list
  is a good starting taxonomy. Also the **12-angle code review** prompt is worth
  studying for your stage-7 evaluation agent.
- **Avoid / lessons.** Compliance frameworks bloat the prompt. Don't pre-load
  all 13; gate them behind a profile flag so non-regulated projects don't pay
  the token cost.

### 1.4 `barkain/claude-code-workflow-orchestration`

- **What it is.** Hook-based delegation framework that *enforces* task
  delegation to specialized agents via Claude Code's hook mechanism. 8
  specialized agents.
- **Borrow from it.** The **adaptive-nudge** pattern: silent → hint → warning →
  strong reminder, instead of hard blocks. They explicitly moved away from
  hard-blocking enforcement because it broke flow. Your `pre-tool-write.py`
  design-token audit should consider this — block on critical violations
  (raw hex colors in committed code), nudge on softer ones.
- **Avoid / lessons.** Their SessionStart hook originally injected ~6.6K tokens
  on every start. They consolidated to a 1.1KB stub + on-demand 7.5KB full
  loader. **Token budgeting in session-start is critical** — your <2000 token
  session context goal is good; don't drift from it.

### 1.5 `ClaudeClaw` (sbusso)

- **What it is.** Persistent agent orchestrator plugin for Claude Code. ~8K
  lines, multi-channel routing (Slack/WhatsApp/Telegram/Discord/Gmail),
  OS-level sandbox isolation (Seatbelt on macOS, bubblewrap on Linux), structured
  memory.
- **Borrow from it.** The **"entire codebase fits in Claude's context for
  self-improvement"** constraint as a design principle. This is a strong forcing
  function — Forge could adopt a similar rule for the plugin's own source
  (the meta-loop you mentioned in chat `db71c227`). Also the channel-adapter
  pattern matches your v4.1 SRS Channel Adapter Layer (§3.14) — even though
  it's out of scope for plugin v0.1, this is the reference design.
- **Avoid / lessons.** Multi-channel adds a *lot* of surface area. They got
  away with it by keeping the kernel ~8K lines. If you ever add channels,
  keep the dispatcher dumb and put logic in channel-specific extensions.

### 1.6 CC Mirror

- **What it is.** Open-source version of Claude Code's internal multi-agent
  orchestration. Implements Fan-Out, Pipeline, and Map-Reduce patterns with
  a "Conductor" identity. Zero external dependencies — runs on task JSON
  files + Claude Code's native background execution.
- **Borrow from it.** The **three orchestration topologies** (Fan-Out / Pipeline /
  Map-Reduce) — your 12-stage pipeline is Pipeline mode by default, but the
  stage-3 architecture agent could fan-out to evaluate alternatives, and
  stage-6 implementation could map-reduce across tasks. Document which topology
  each stage uses.
- **Avoid / lessons.** They store everything in task JSON files; that's
  brittle to manual edits. Your `state.md` with frontmatter is more
  human-editable but slower to parse. Trade-off is real; pick deliberately.

### 1.7 The aggregator repos worth bookmarking

- **`rohitg00/awesome-claude-code-toolkit`** — 135 agents, 35 skills, 42
  commands, 176+ plugins. Use as a search index when you suspect "someone has
  built this." Updated weekly.
- **`ComposioHQ/awesome-claude-skills`** — Curated skills, including
  `great_cto` and similar SDLC plugins. Higher signal, less volume.

---

## Layer 2 — Spec-Driven Development frameworks (Stage 1–4 inspiration)

Forge's stages 1 (SRS), 2 (Product+UX), 3 (Architecture), 4 (Spec) are SDD.
This is the most mature category in the agent tools space — borrow heavily.

### 2.1 GitHub Spec Kit

- **What it is.** GitHub's official SDD toolkit. Spec → Plan → Tasks →
  Implement, with a "Constitution" rulebook. 93K+ stars, v0.8.7 (May 2026)
  supports 30+ coding agents including Claude Code.
- **Borrow from it.** The **Constitution document** — a top-level set of
  inviolable project rules that every agent reads first. Forge's CLAUDE.md
  partly fills this role, but Spec Kit's separation of "principles" from
  "context" is cleaner. Also: their slash-command shape `/specify`, `/plan`,
  `/tasks`, `/implement` maps almost 1:1 to your `/forge:srs`, `/forge:plan`,
  etc.
- **Avoid / lessons.** Spec Kit is tool-agnostic, which means it gives up
  Claude-Code-specific optimizations (subagents, hooks, skills). Forge is
  Claude-Code-native — don't apologize for that, it's a feature.

### 2.2 Kiro IDE (AWS)

- **What it is.** VS Code fork with built-in SDD. Outputs `requirements.md`,
  `design.md`, `tasks.md` from natural language. Hooks and MCP servers
  native. Privacy-first.
- **Borrow from it.** The **three-file convention** (requirements, design,
  tasks) is simpler than your 12-stage tree. If users complain Forge's
  pipeline is too heavy, you can offer a Kiro-style "lite" profile that
  collapses stages 1–4 into three files. Also: Delta's reported 1,948%
  adoption growth came from spec-first, *not* from the IDE itself — meaning
  the workflow wins over the tool.
- **Avoid / lessons.** Kiro is locked to VS Code as the host. Forge's
  decision to run in Claude Code CLI means it works in any terminal, any
  editor — keep that portable surface clean.

### 2.3 BMAD Method

- **What it is.** Agile AI-driven development framework. 12+ specialized
  agent personas, 50+ guided workflows, "Party Mode" multi-agent
  collaboration. V6 has a Cross Platform Agent Team working across Claude
  Code, Cursor, Codex.
- **Borrow from it.** **Party Mode** — multiple agents in conversation
  resolving a decision together. This is your stage-3 architecture review
  pattern: have the architect, security, and DevOps agents debate before
  committing to an architectural choice. Also: 50+ guided workflows is
  more than you need, but study which 12-ish they actually use most.
- **Avoid / lessons.** BMAD's 12 personas overlap heavily (e.g.
  product-manager vs business-analyst vs scrum-master). Forge's 12 stage
  agents + 4 cross-stage is tighter; resist the urge to add more roles.

### 2.4 OpenSpec (Fission-AI)

- **What it is.** "Most loved spec framework." 25+ supported tools. The
  innovation: **delta specs** — describing *changes* to a system rather
  than full specs, making it practical for brownfield projects.
- **Borrow from it.** Forge's current SRS treats projects as greenfield
  (Stage 1 starts from idea). For brownfield use, you need a delta-spec
  mode — Stage 1 should accept "here's an existing system; here's what's
  changing." Add this to your roadmap; OpenSpec's delta format is a good
  starting point.
- **Avoid / lessons.** OpenSpec is markdown-only with no enforcement. The
  spec can drift from reality. Forge's gates close this loop, but only if
  you actually enforce them — your `check-gate.py` is the critical piece.

---

## Layer 3 — Multi-agent orchestration (your 16 agents)

### 3.1 CrewAI

- **What it is.** 25K+ stars. Role-playing autonomous AI agents.
  Independent of LangChain. Production-grade "Flows" abstraction.
- **Borrow from it.** **Role + Goal + Backstory** as the agent definition
  schema. Your agent frontmatter probably already does this; if not, copy
  the structure. CrewAI's `tools` field per agent (restricting which tools
  each agent can use) is exactly what your agent tool-allow-list should
  look like.
- **Avoid / lessons.** CrewAI tasks were originally serial-only; parallelism
  was an afterthought. Design your task DAG with parallelism from the start
  — `task-dag.md` should express which tasks can run concurrently. You
  have a user skill for `crewai-agent`; treat it as authoritative on the
  agent definition format.

### 3.2 OpenHands (formerly OpenDevin)

- **What it is.** Community platform for AI-driven development. SDK + CLI
  + local GUI. REST API. Cloud and enterprise deployments.
- **Borrow from it.** The **sandbox-first** execution model — every agent
  action runs in a sandbox before being committed. Forge's
  `pre-tool-write.py` is a lightweight version of this; if you ever go
  beyond design-token audits, OpenHands' sandbox patterns are the
  reference.
- **Avoid / lessons.** OpenHands got heavy fast. The local GUI was a
  distraction from core agent quality. Forge's v0.1 "CLI only" non-goal
  is the right call — keep it that way until the agent loop is rock solid.

### 3.3 OpenCognit

- **What it is.** Open-source AI agent OS. Runs a "virtual company" — CEO
  orchestrator, specialist agents, persistent memory via Rooms (KV), Diary
  (timeline), Knowledge Graph.
- **Borrow from it.** The **three memory shapes** — KV (Rooms), timeline
  (Diary), graph (Knowledge Graph) — map cleanly to your three-tier
  memory:
  - Session context = KV (small, hot)
  - Project files (`pipeline/`, `tasks/`) = timeline (sequential, append-mostly)
  - `~/.forge/lessons.yaml` = knowledge graph (relational, cross-project)
  Adopt this vocabulary in your docs; it's clearer than "tier 1/2/3."
  Also: **atomic budgets per agent** (token + dollar caps) is something
  Forge doesn't have yet and should consider for stage agents that can
  loop.
- **Avoid / lessons.** OpenCognit's "virtual company" framing is fun but
  oversold. Real CEO-style orchestration adds latency and failure modes
  (CEO bottleneck, delegated work that gets misinterpreted). Your 12-stage
  pipeline is more deterministic; don't slip into agent-driven dispatch
  unless you have a reason.

### 3.4 AutoGPT

- **What it is.** Pioneered autonomous agent loops. Now evolved into a
  platform with a low-code builder + marketplace.
- **Borrow from it.** Mostly historical. The main lesson is **what not to
  do** (next section).
- **Avoid / lessons.** Original AutoGPT spawned infinite agent loops
  burning tokens with no progress. The fix was **explicit termination
  conditions and budget caps**. Every Forge agent that can spawn subagents
  or loop (Reflector, Implementation agent, Resolve agent) needs both.

---

## Layer 4 — Deterministic runtime & event sourcing (your `state.md` log)

This is where your v4.1 SRS's "Event Sourcing (§3.22)" and "Proposal/
Validator/Executor (§3.23)" live. Out of scope for plugin v0.1, but the
prior art here will inform when you do add it.

### 4.1 L0 (ai-2070)

- **What it is.** "Missing reliability substrate for AI." Wraps any AI
  stream (OpenAI, Anthropic, 100+ providers via LiteLLM) with byte-for-byte
  replays, atomic event logs, retries, fallbacks, consensus, guardrails.
  3,000+ tests in TS alone. Both Python and TypeScript.
- **Borrow from it.** The **byte-for-byte replay** primitive. Even
  without adopting L0, you can structure `state.md` writes so that re-running
  a stage with the same inputs and seeded RNG produces the same outputs.
  This matters for debugging "why did the agent decide X here?"
- **Avoid / lessons.** Deterministic replay is hard. L0 took multiple years.
  Don't half-build it; either commit (post-v0.1) or skip it. Your current
  `state.md` + JSONL pattern log is the right "skip it for now" answer.

### 4.2 Exarchos (lvlup-sw)

- **What it is.** Local-first SDLC workflow harness with concurrent
  event-sourced process manager. Persistent state survives context overflow.
  Append-only event log. CLI universal agent interface.
- **Borrow from it.** **Append-only event log** as the state representation.
  Your `state.md` is currently mutable markdown with a history table —
  workable, but a JSONL append-only log alongside it would give you replay
  for free. The v4.1 SRS already lists this; Exarchos is the reference.
- **Avoid / lessons.** Exarchos' "cooperative agents" model (agents that
  yield to each other) added complexity. Your pipeline is sequential by
  default — keep it that way unless parallel stages become a bottleneck.

### 4.3 `truongnat/agentic-sdlc`

- **What it is.** Deterministic local execution runtime for agentic
  software workflows. Replay store (10× faster, $0 cost). 6 LLM providers.
- **Borrow from it.** **Replay store as a cost optimization**. Cached
  responses to identical prompts cut development feedback loops 10×. Your
  pipeline reruns the same prompts a lot during development — a local
  prompt-cache layer (even just SHA-256 of prompt → response) would speed
  up your own dogfooding significantly.
- **Avoid / lessons.** Their "perfect determinism" claim only holds with
  temperature=0 and seeded sampling. Document this constraint clearly if
  you adopt replay.

---

## Layer 5 — Memory & reflection systems (your Reflector, lessons.yaml)

This is the deepest research area. Read at least one paper here before
finalizing the `stop-reflect.py` design (T-009).

### 5.1 Reflexion (Shinn et al., 2023)

- **What it is.** The seminal paper on agents that generate "reflection"
  summaries after each episode (what went wrong, why, how to improve) and
  store them for retrieval in future tasks. Self-RL via verbal feedback.
- **Borrow from it.** The **reflection schema**: each reflection has
  (a) what happened, (b) why it went wrong, (c) what to do differently.
  Your `lessons.yaml` schema should match — anything else is missing the
  causal piece that makes reflections actionable.
- **Avoid / lessons.** Reflexion stored *every* reflection. Most are noise.
  You need a **durability gate** — a reflection only graduates to a
  persistent lesson after surviving N reflection cycles (see bswen guide
  below). This is exactly the role of your Lesson Extractor agent.

### 5.2 ExpeL (Experiential Learning)

- **What it is.** Extension of Reflexion that extracts *generalizable
  insights* from specific reflections — moves from "this prompt failed in
  this case" to "this prompt pattern fails when X."
- **Borrow from it.** Two-stage extraction: raw reflection → generalized
  rule. Your Lesson Extractor → Skill Miner pipeline is doing the same
  thing. ExpeL's prompt for "what's the general pattern here?" is worth
  studying.
- **Avoid / lessons.** Over-generalization fails silently. A rule that
  says "always X" derived from 3 examples may break on the 4th. Tag
  lessons with evidence count and confidence; surface low-confidence ones
  for human review.

### 5.3 MemGPT / Letta

- **What it is.** OS-inspired memory architecture. Main context = "RAM",
  recall DB = "disk", archival storage = "cold storage." Agent manages its
  own paging.
- **Borrow from it.** The **mental model** — your three-tier memory
  matches MemGPT's structure. The vocabulary "paging from disk to RAM"
  may help users understand what's happening.
- **Avoid / lessons.** Multiple production reports (Towards Data Science,
  March 2026) say MemGPT's manual tier management is *burdensome and tends
  to fail*. **Concrete lesson:** don't make agents responsible for paging
  decisions. Forge's design — file-system as source of truth, hooks load
  relevant files at session-start — is the safer pattern. Keep it.

### 5.4 Mem0

- **What it is.** Production memory framework. Open source. State of AI
  Agent Memory 2026 report from this project is worth reading in full.
- **Borrow from it.** Two production-tested defaults from the Mem0
  changelog:
  - **Async memory writes by default.** Sync writes block the response
    pipeline and add latency users feel. Your `stop-reflect.py` should
    return control quickly and write reflections in background.
  - **Reranking matters.** Vector similarity returns candidates, but the
    ordering is often wrong. If you ever add semantic search over
    `lessons.yaml`, plan for a rerank step.
- **Avoid / lessons.** Mem0 added a lot of features (reranking, async,
  multiple stores) over 18 months. Many were retrofits. Design Forge's
  memory with these in mind from day one rather than discovering them
  later.

### 5.5 Hindsight (Vectorize)

- **What it is.** Memory engine specifically designed for *institutional
  knowledge* (lessons, patterns, domain expertise) rather than
  personalization. Built around the harder problem first.
- **Borrow from it.** The distinction between **personalization memory**
  (who is this user, what do they prefer) and **institutional memory**
  (what does this project know). Forge's `lessons.yaml` is institutional;
  per-project preferences in `~/.forge/profiles/` are personalization.
  Keep these stores separate.
- **Avoid / lessons.** Hindsight notes that most memory frameworks started
  with personalization and added institutional features later, leading to
  awkward bolt-ons. You're doing it in the right order — don't let
  personalization features creep into `lessons.yaml`.

### 5.6 bswen reflection guide

- **What it is.** A practical engineering guide (March 2026) for building
  reflection systems. Three-tier architecture: index → reflections → memory
  logs. **Durability gate** — only insights that survive multiple cycles
  get promoted to permanent behavior.
- **Borrow from it.** The **durability counter** is the key idea your
  Lesson Extractor needs. A naive implementation promotes every reflection
  to a lesson; better implementations require the same pattern to be
  observed N times before it becomes a rule. Adopt this from T-009.
- **Avoid / lessons.** Without a durability gate, your `lessons.yaml`
  fills up with one-off observations that hurt more than they help. The
  gate is the difference between useful learning and noise.

---

## Layer 6 — Governance, gates & policy (your Gate Checker)

### 6.1 Microsoft Agent Governance Toolkit

- **What it is.** Runtime governance for AI agents. Deterministic policy
  enforcement, zero-trust identity, sandboxing. Covers all 10 OWASP
  Agentic AI risks. 13K+ tests. Sub-millisecond policy evaluation.
  Released April 2026; aligned with EU AI Act (August 2026) and Colorado
  AI Act (June 2026) timelines.
- **Borrow from it.** The **policy-as-data** pattern — gates are declarative
  rules evaluated against agent actions, not code. Your `gate-criteria.md`
  is YAML, which is the right shape; consider adopting Microsoft's OWASP
  Agentic categories as a taxonomy for *what kinds* of gates exist
  (prompt injection, excessive agency, etc.).
- **Avoid / lessons.** Sub-millisecond enforcement requires policies be
  cacheable and stateless. Don't write gates that need to load files or
  call out to LLMs — keep gate checks pure functions.

### 6.2 Agent Swarm Kit (tripolskypetr)

- **What it is.** TypeScript library for framework-agnostic multi-agent
  systems. MCP-ready. Redis storage. Human-operator escalation.
- **Borrow from it.** The **human-operator escalation** pattern — when
  the swarm can't decide, escalate to a human with full context. Your
  gate failures should follow this pattern: gate fails → present the
  failure + suggested fixes + "forced advance" override option to the user.
- **Avoid / lessons.** Redis storage couples them to a server. Your
  file-system approach is simpler and works offline; don't trade it for a
  database without strong reason.

---

## Cross-cutting lessons (the meta-list)

These showed up across multiple projects. Treat them as Forge's "external
lessons learned" — apply them before re-discovering them.

1. **Spec is the source of truth, never chat.** Claude Code is stateless
   between sessions. The spec file on disk survives. Forge's `pipeline/`
   tree already encodes this — protect it.

2. **Hooks are guardrails, not enforcers.** Hard blocks break flow.
   Adaptive nudges (silent → hint → warning → strong) preserve agency
   while still pushing the right behavior. (barkain plugin lesson.)

3. **Token budget at session-start is critical.** Aim for <2K tokens of
   injected context. Load full skill/agent files on-demand. (barkain
   trimmed 6.6K; you've set <2K as a goal — defend it.)

4. **Don't store every reflection. Use a durability gate.** Most
   reflections are one-off noise. Lessons that survive multiple cycles
   are actually useful patterns. (bswen, Reflexion lessons.)

5. **Memory writes are async by default.** Don't block the response on
   reflection storage. (Mem0 lesson.)

6. **Atomic budgets per agent.** Every agent that can loop or spawn
   subagents needs token + dollar caps. (AutoGPT lesson.)

7. **Don't make agents manage memory tiers.** File system is the source
   of truth; hooks load context. Don't ask the agent to decide what to
   page in and out — that's where MemGPT-style systems fail.

8. **Verify OSS claims.** Atlas-OS markets itself as MIT but ships
   minified binaries. Check that source matches license before adopting
   any dependency.

9. **Replay caches save real money during development.** A SHA(prompt) →
   response cache for dev mode is the cheapest win available.
   (agentic-sdlc lesson.)

10. **Don't pre-load all profiles/compliance frameworks.** Gate them
    behind a flag. (great_cto lesson — 13 compliance frameworks bloat
    every prompt if always loaded.)

11. **Plan multi-repo support last, not first.** It's the source of most
    config complexity in closedloop-ai/claude-plugins. Forge v0.1 single-repo
    scope is correct.

12. **Match orchestration topology to stage.** Stages are not all
    Pipeline — Stage 3 (architecture) is often Fan-Out (consider N
    options, pick one), Stage 6 (implementation) is often Map-Reduce
    (parallel tasks → merge). Document which is which. (CC Mirror
    insight.)

---

## What's intentionally not here

- **LangChain / LangGraph** — too general-purpose; lessons don't transfer
  cleanly to Forge's narrow scope.
- **n8n / Zapier-style automation** — different paradigm (deterministic
  workflows, not agentic).
- **AutoGen (Microsoft)** — large overlap with CrewAI; if you've read
  CrewAI, you've covered ~80% of AutoGen's patterns.
- **AgentOS / various agent OS forks** — most are unverifiable or pre-alpha.
  If one becomes notable, add it.

---

## Refresh policy

This map is dated **May 2026**. The agentic AI tools landscape moves fast —
several of these projects didn't exist 12 months ago. Schedule a refresh
every 3 months during active Forge development; check the two awesome-lists
in §1.7 first for the highest-signal new entries.
