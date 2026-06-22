# Additive Aegis Items for forge-os (core-untouched backlog)

> **Decision context:** Owner chose **Path A** (continue local-first forge-os; native Phase 11
> next). **Path B** (separate `aegis` service embedding forge-os) is deferred to the future.
> Hard constraint: **never mutate the core.** Produced 2026-06-22. Companion to
> `AEGIS-VS-FORGEOS-GAP-ANALYSIS.md`.

## What "never mutate the core" means here

In forge-os, **"the core" = `src/forge_os/core/` (StateManager + state ownership) and
`src/forge_os/schemas/` (the Pydantic contracts).** Everything below plugs into an existing
**extension seam** so those two never change:

| Seam | How you extend it | Example |
|---|---|---|
| **Adapter registry** (`adapters/registry.py`) | register a new adapter with optional-dep guard | new model providers |
| **Extension/plugin system** (Phase 11) | drop-in plugin + manifest + permission validation | anything third-party |
| **Gate types** (`gates/` dispatch by `gate.type`) | add a gate type handler | new quality gates |
| **Event types** (append-only `events/`) | append a new `EventKind` | new lifecycle signals |
| **CLI sub-app** (`cli/commands/<x>.py` + `use_cases/`) | new Typer sub-app + use case | new `forge <verb>` |
| **New sibling domain module** | a package core never imports | `adlc/`, `tools/`, `knowledge/` |

The cleanest story: **build Phase 11's plugin system first, then deliver additive items _as
plugins_** — proving the seam and keeping the core frozen by construction.

## The backlog (ranked by value × fit)

Legend — Core: always **No**. LF (local-first): ✅ local / ⚠️ opt-in network only.
Effort: S/M/L.

| # | Item | Aegis origin | forge-os home (seam) | LF | Effort |
|---|---|---|---|---|---|
| 1 | **Extension/plugin lifecycle** (manifest, `forge plug`, permission validation) | Ph2 S2.1 | **Phase 11** — new `extensions/` module + CLI | ✅ | M |
| 2 | **Local model providers** (Ollama, vLLM, LM Studio) | Ph2 S2.2 | adapter registry → new adapter pkgs | ✅ | M |
| 3 | **Cloud providers as opt-in extras** (OpenAI, Gemini, Azure, OpenRouter) | Ph2 S2.2 | adapter registry + `[project.optional-dependencies]` | ⚠️ | S each |
| 4 | **Embeddings/generate provider interface** | Ph2 S2.2 | new `providers/` capability (separate from spawn-centric adapters) | ✅ (local embed) | M |
| 5 | **ADLC registries** — prompt / dataset / model / eval / experiment tracking | Ph4 ADLC | new `adlc/` domain module + `forge adlc` CLI (YAML/sqlite, like `lessons.yaml`) | ✅ | L (sub-slice) |
| 6 | **Prompt registry (Jinja2)** | Ph4 / Knowledge | `prompts/` dir + `adlc/prompts` — matches `.claude/rules/llm-prompts.md` exactly | ✅ | S |
| 7 | **Cost-tracking ledger** (`.forge/cost.jsonl`, `forge cost report`) | "Cost Layer" | new use_case + CLI; reads existing per-run token/cost events | ✅ | S |
| 8 | **Tool registry** (declarative, permission-gated) | Tool Registry | new `tools/` module; integrates `SecurityEnforcer` via DI | ✅ | M |
| 9 | **Evaluation runner** (golden sets, scoring) — distinct from gates | Eval Layer | `adlc/eval` or `eval/` module | ✅ | M |
| 10 | **Configurable memory eviction/retention** | Ph4 S4.2 | extends `memory/` + `context/pruner` (domain module, not `core/`) | ✅ | S–M |
| 11 | **Artifact versioning/metadata/search** | Ph4 S4.3 | extends `context/registry` ADG (domain module) | ✅ | M |
| 12 | **KG-lite semantic search** (sqlite + local embeddings, **no Neo4j**) | Ph4 S4.1 | new `knowledge/` module | ✅ | L |
| 13 | **Knowledge connectors** (local files/PDF/MD; GitHub/Jira opt-in) | Knowledge | plugins (post-Phase 11) | local ✅ / net ⚠️ | M |

## Explicitly NOT a clean additive (do not attempt under Path A)

- **Generic parallel/DAG/event-driven Workflow Engine** (Aegis Workflow Engine) — forge-os
  has a *stage* machine; replacing it with a generic DAG engine **touches orchestration
  core**. Not additive. Revisit only as a deliberate core redesign, not a bolt-on.
- **Multi-tenant RBAC/ABAC · FastAPI-as-primary · Postgres/Redis/OpenSearch/MinIO/Neo4j ·
  K8s/Helm/Terraform · OTel/Prometheus/Grafana/Loki · web UI** → these belong to **Path B**
  (separate `aegis` repo embedding forge-os). They break ADR-001 + L004 if forced into core.

## Recommended sequencing

1. **Phase 11 (now):** plugin system **first** (P11.15–19) → channels (P11.01–07) → OpenClaw
   interface+mocks (P11.08–14, blocked on external API). Plugin-first because it's the
   highest-value Aegis-convergent item and the delivery vehicle for everything below.
2. **Phase 12.5 / 13 (post-11), delivered _as plugins_ to exercise the new seam:**
   - quick wins: **#7 cost ledger**, **#6 prompt registry**
   - then **#2 local providers**, **#5 ADLC model/dataset registries**
3. **Later / optional:** #4 embeddings, #8 tool registry, #9 eval runner, #12 KG-lite.
