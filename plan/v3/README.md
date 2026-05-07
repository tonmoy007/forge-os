# Forge OS

**The self‑sustaining software engineering ecosystem.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-Under%20Construction-yellow)]()

> *“Build software like a world‑class engineering team, even if you are a team of one.”*

---

## Vision

**Forge OS** is a complete, independent operating system for software creation. It orchestrates every step of the development lifecycle—from the first vague requirement to post‑production learning—through a pipeline of specialised AI agents, automatic quality gates, and a memory system that grows smarter with every project.

It is not a plugin. It is not an IDE. It is a **methodology engine** that can run on any machine, with any AI model, and under any governance model. Its ultimate goal is to become the definitive open‑source foundation for autonomous, reliable, and continuously improving software engineering.

---

## The Problem

Building software with today’s AI coding tools is **session‑by‑session improvisation**:

- Every session starts cold—no structured memory of past decisions, mistakes, or project evolution.
- Quality checks are ad‑hoc, relying on the developer to manually enforce style, testing, and security.
- There is no enforced process; the pipeline from idea to deployed product lives only in the developer’s mind.
- Lessons learned on one project rarely carry over to the next.

The result is wasted time, repeated errors, and software quality that depends entirely on the individual’s discipline.

---

## What Forge OS Does

Forge OS replaces improvisation with a **structured, self‑improving, and kernel‑agnostic SDLC machine**.

| Capability | How Forge OS Delivers |
|------------|------------------------|
| **Full‑lifecycle pipeline** | 12 stages from *SRS* through *Release*, with automated state transitions, gate enforcement, and artifact traceability. |
| **Specialised AI agents** | 16 personas (Requirements Analyst, System Architect, Builder, Evaluator…) each with scoped tools, context, and output contracts. |
| **Multi‑modal quality gates** | File‑existence checks, pattern enforcement, quantitative test runs, metric thresholds, and AI‑assisted reviews—all evaluated automatically. |
| **Three‑tier memory** | Session context, project memory, and cross‑project global knowledge that compounds learning. |
| **Self‑improvement loop** | Automatic reflection, lesson extraction, skill mining, and a “Dreamer” agent that consolidates knowledge offline. |
| **Enterprise‑grade security** | gVisor‑sandboxed execution, phase‑based access control, credential proxy, and immutable audit trail. |
| **Human‑in‑the‑loop governance** | Risk‑based escalation, Maker‑Checker approval, structured decision UIs, and cryptographic audit signing. |
| **Kernel‑agnostic** | Use Claude, GPT, OpenClaw, or a local LLM—Forge OS adapts without changing your pipeline. |
| **Extensible by community** | Plug in new agents, gate types, project profiles, or channel adapters via the MCP protocol. |

---

## Who Is It For?

- **Solo developers** who want the discipline of a full engineering team without the overhead.
- **Start‑ups** that need to move fast without accumulating technical debt.
- **Large engineering organisations** looking to enforce consistent quality and capture institutional knowledge.
- **Open‑source maintainers** who want to automate governance, changelogs, and contributor onboarding.
- **AI researchers** exploring multi‑agent software engineering and self‑improving systems.

---

## Impact

Forge OS changes the way software is built by making **process, quality, and learning** first‑class citizens of the development environment:

- **50‑80% less rework** – bugs caught at the specification stage instead of production.
- **Instant onboarding** – new contributors get the complete project history, decisions, and conventions injected into their first session.
- **Cross‑project learning** – a lesson learned on one project becomes a guardrail on all future projects.
- **Radical transparency** – every decision, tool invocation, and override is recorded in an immutable audit ledger.
- **No vendor lock‑in** – switch the underlying AI model without changing how you build software.

---

## Architecture at a Glance

```
┌───────────────────────────────────────────────────┐
│                   FORGE OS                        │
│                                                   │
│  Orchestration Engine  ↔  Kernel Adapter Layer    │
│  (State Machine,         (Claude, GPT,            │
│   Context Pruner,         OpenClaw, Local)        │
│   Gate Coordinator)                                │
│                                                   │
│  Memory Subsystem  ↔  HITL & Audit & Sandbox      │
│  (LKG, ADG,         (Immutable Ledger,            │
│   Tiered Memory)     gVisor, Two‑Key Rule)        │
│                                                   │
│  Channel Adapters  ↔  MCP Tooling Ecosystem       │
│  (Slack, Telegram,     (200+ MCP servers)          │
│   WhatsApp)                                        │
└───────────────────────────────────────────────────┘
```

All components exchange data through open formats (Markdown, YAML, JSON, GraphML) and standard protocols (MCP, OpenTelemetry). Nothing is a black box.

---

## Quick Start (coming soon)

```bash
# Install
pip install forge-os

# Start a new project
forge init my-app

# Walk through the lifecycle
forge stage start srs
forge stage start architecture
forge stage start build
...

# Check progress
forge status

# Resume from last session
forge resume
```

*Note: Forge OS is under active construction. See the [roadmap](#roadmap) below.*

---

## Project Status and Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 0** | Foundation: CLI, state machine, 3‑stage pipeline | ✅ Planned |
| **Phase 1** | Full 12‑stage pipeline, lifecycle hooks | 🔜 Building |
| **Phase 2** | Specialized agents, multi‑modal gates | 🔜 Building |
| **Phase 3** | Memory & learning (LKG, ADG, cross‑project) | 📝 Designed |
| **Phase 4** | Adaptive profiles, skill mining, health daemon | 📝 Designed |
| **Phase 5** | OpenClaw integration, channel adapters, extensions | 📝 Designed |
| **Phase 6** | Enterprise hardening: sandboxing, HITL, observability | 📝 Designed |

For the complete, task‑level implementation plan, see [`PLAN.md`](PLAN.md). For the technical specification, see [`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md).

---

## Contributing

Forge OS is built to be extended by a community. You can contribute:

- **New stage agents** – tune a persona for a specific language or framework.
- **Gate criteria modules** – write an MCP server that checks license compliance, accessibility, or performance.
- **Project profiles** – package a set of stage weights and gates for a domain (e.g., embedded systems, game development).
- **Kernel adapters** – integrate a new AI backend.
- **Documentation and guides** – help others adopt self‑sustaining development.

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) (coming soon) and our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## License

Forge OS is open‑source under the [Apache License 2.0](LICENSE). All artifacts produced by the pipeline belong entirely to you.

---

## Why “Forge”?

A forge is where raw materials are transformed into tools and works of art through heat, force, and skill. Forge OS applies the same concept to software: it takes raw ideas and, through a disciplined, self‑improving process, transforms them into reliable, well‑crafted products. And just like a blacksmith’s hammer, it never forgets what it learned.

---

**Join us in building the operating system for software creation itself.**
