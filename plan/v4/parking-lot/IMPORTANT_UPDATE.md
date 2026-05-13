> **PARKED — 2026-05-13**
> This document is superseded. CocoIndex was rejected (`tasks/lessons.md` L004 — requires PostgreSQL, incompatible with local-first design); ClawVault/Ruflo "INSPIRE" tracks (T-035, T-037) and ACP roadmap entries (T-034, T-036) are deferred pending the strategic decision recorded in `STATUS.md`. See `plan/v4/parking-lot/README.md` for parking policy.
> Inline corrections below preserve historical context; **do not implement these tasks without re-opening the v4 spec freeze**.

## The framework

Three options per vendor, picked by these tests:

| Decision | When to pick it |
|---|---|
| **Buy (vendor it)** | Vendor has a stable API, the form factor is plug-compatible (MCP, CLI, REST), and building it would dwarf consuming it |
| **Inspire (steal the design)** | The value is in the *design* (taxonomy, algorithm, pattern), not the *code*. Native reimplementation is straightforward and gives you total control |
| **Defer** | Real capability, but not on the critical path right now |

Applied to your stack:

| Vendor | Decision | Why |
|---|---|---|
| **CocoIndex** | **REJECTED** (2026-05-12, `lessons.md` L004) | Requires PostgreSQL for its metadata store, which conflicts with Forge OS's local-first / zero-infrastructure design (ADR-002). The MCP path was considered but the underlying engine still imposes the database dependency. Replaced by the in-process mtime+content cache in `src/forge_os/context/pruner.py`. Tree-sitter chunking + AST-fingerprinted semantic staleness remain unbuilt — track as a separate decision if/when the indexing limitation becomes load-bearing. |
| **ClawVault** | **INSPIRE** — steal the design, implement natively | The value isn't the code; it's the **design**: 8-type taxonomy, observation→score→route pipeline, four workers (Curator/Janitor/Distiller/Surveyor), checkpoint/wake/sleep primitives, vault directory schema. Implementing these natively in Python is ~3-4 weeks. Vendoring it brings a Node.js/Bun runtime dependency and ties your vault schema to upstream changes. Their `clawvault-py` Python SDK is thin and lags behind the npm package. |
| **Ruflo** | **INSPIRE** — steal the Queen-Worker pattern only | Don't vendor it. Ruflo IS Claude Code subprocesses with `--dangerously-skip-permissions`. Issue #368 shows the spawn sometimes doesn't actually parallelize. Adds a complex orchestration layer that doesn't compose cleanly with your hook-based dispatcher — Ruflo wants to BE the orchestrator, not be orchestrated. The valuable concept (strategic / tactical / adaptive queens + specialized workers) is ~1 week of work to add to your dispatcher. |
| **ACP** | **DEFER** | Your plugin is currently Claude-Code-native and that's a deliberate scope choice. ACP is "make Forge available in Zed/JetBrains too" — a v2 feature. v0.11.x is still moving; HTTP remote-agent transport isn't stable. Revisit when (a) someone asks for it, or (b) ACP hits a v1.0 freeze. |
| **AIVS** | **WATCH** — don't depend, don't even reference yet | W3C Community Group + IETF I-D = no policy weight. The HMAC chain idea you already have is essentially what AIVS specifies. If they standardize, you adopt their format; until then, ignore. |

## What this gives you

```
Your Forge Plugin (Python, Claude Code native)
│
├── Hooks (yours — 7)
├── Skills (yours — 16)
├── Agents (yours — 16 personas)
│
├── Memory: vault/ (ClawVault-INSPIRED, native Python)
│   ├── 8-type taxonomy (adopted)
│   ├── Observation → score → route pipeline (rebuilt)
│   ├── 4 workers (rebuilt: Curator hourly, Janitor + Distiller nightly, Surveyor weekly)
│   ├── Checkpoint/wake/sleep primitives (rebuilt)
│   └── Markdown + YAML frontmatter (adopted)
│
├── Indexing: CocoIndex Code MCP (BOUGHT — one MCP server)
│
├── Parallel execution: extended hook dispatcher (Ruflo-INSPIRED)
│   └── Queen-Worker pattern as an optional "swarm mode" for Stage 6
│
├── Safety (BUILT from primitives, per v4.1)
│   ├── Proposal/Validator/Executor (from T-009 hardening)
│   ├── Event log .forge/events.jsonl (HMAC chain)
│   └── OPA later — only if you hit governance complexity
│
└── Interop: Claude Code only (ACP DEFERRED)
```

**Runtime dependency count:** Python 3.12+, one optional MCP server (CocoIndex). That's it. No Node.js, no Postgres+pgvector (CocoIndex Code's MCP supports SQLite mode), no Ruflo, no Keycloak. Matches your constraint.

**What you give up by inspiring rather than buying ClawVault:**
- ~3-4 weeks of implementation work
- The `clawvault` CLI for ad-hoc commands (you'd have your own `forge vault` commands instead)
- Future ClawVault feature releases (you'd cherry-pick them as your own features later)

**What you gain:**
- Pure Python, no Node.js dependency
- Vault schema you control — won't be broken by upstream
- Tighter integration with your existing state.md, lessons.md, .forge/ structure (much of which already mirrors ClawVault's concepts anyway)
- One less project's bugs to debug

## Specific calls for your roadmap

Looking at where you are (just past T-014, working on agents → skills → e2e):

| Task adjustment | What to do |
|---|---|
| **T-002 (forge-init)** | Already scaffolds `pipeline/`, `tasks/`, `.forge/`. **Add `vault/` subdirectory creation** with the 8 ClawVault-inspired folders: `decisions/`, `lessons/`, `people/`, `projects/`, `tasks/`, `backlog/`, `handoffs/`, `inbox/`. Markdown + frontmatter. |
| **New T-034: Observation pipeline** | Replace your current lesson-extraction-only approach with full observation → score → route. Score uses three tiers (🔴 0.8+, 🟡 0.4-0.79, 🟢 <0.4) — copy ClawVault's because it works. |
| **New T-035: Workers** | Curator (hourly via daemon), Janitor (nightly, prune dormant), Distiller (nightly, merge near-duplicates), Surveyor (weekly, cross-stage patterns). All as Python modules called from your daemon scheduler. All write through the proposal boundary from T-009-hardened. |
| **New T-036: CocoIndex Code MCP integration** | Add to `forge-init` an optional step: "Add CocoIndex Code MCP for semantic code search? [Y/n]". If yes, `claude mcp add cocoindex-code -- ccc mcp` and add MCP usage docs to CLAUDE.md template. |
| **New T-037: Queen-Worker swarm mode** | Extend your dispatcher with a `--swarm` flag for Stage 6 that spawns N parallel subagents with a coordinator persona. Three coordinator variants: strategic (decomposition), tactical (sub-delegation), adaptive (gate-feedback-driven). Off by default. |
| **No T-038 for ACP** | Track as v0.2 ticket: "Expose plugin via ACP for non-Claude-Code editors." |

That keeps your milestone count modest — four new tasks, no abandoned work, every existing task still valid.

## How to apply this heuristic going forward

When the next shiny project appears (and it will — the space is moving fast):

1. **Is the value in the API or the design?** API → buy. Design → inspire.
2. **Does it add a runtime dependency to a different language/stack?** If yes → strong bias toward inspire-only unless the API is genuinely deep.
3. **Can your users add it themselves with one command?** (MCP servers, CLI tools.) If yes → don't vendor it; document it as an optional integration.
4. **Is the upstream stable, or still moving?** Pre-1.0 protocols (ACP at 0.11) → defer; let them stabilize.
5. **Does the abstraction compose with yours, or fight it?** Ruflo wants to *be* the orchestrator — that fights your hook model. CocoIndex MCP is content with being a data source — that composes cleanly.

The decision you're making isn't "lock in to vendor X" — it's "what's the smallest set of moving parts that delivers the most value." Right now that's: **buy CocoIndex (one MCP), inspire ClawVault + Ruflo (native Python), defer ACP, build the safety primitives.** Three weeks of design adoption + one command install gets you the entire v4.0 ClawVault track's concepts without inheriting its dependency tree.
