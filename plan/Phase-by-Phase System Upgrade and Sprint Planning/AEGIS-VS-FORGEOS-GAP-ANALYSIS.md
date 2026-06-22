# Aegis Lifecycle ↔ forge-os Gap Analysis

> **Purpose:** Reconcile the dropped-in "Aegis Lifecycle" roadmap (Phases 1–7) against
> what forge-os **already ships**, so we don't rebuild existing modules or silently pivot
> the product. Produced 2026-06-22 in response to the owner's "reconcile first" decision.
>
> **Evidence base:** `src/forge_os/` module tree, `pyproject.toml` deps, `tasks/lessons.md`
> (L004), `plan/CURRENT_PHASE.md`. All claims below are grounded in the real tree.

## TL;DR verdict

Aegis is **not an upgrade path for forge-os — it's a different product**. Roughly **60% of
Aegis Phases 1–6 is already implemented** in forge-os, in local-first form. The remaining
40% splits into two very different piles:

- **Additive & local-first-compatible** (~15%) — worth pulling in as native phases.
- **Identity-breaking** (~25%) — requires Postgres/Redis/K8s/multi-tenant servers, which
  **directly violate ADR-001 (local-first, kernel-agnostic) and L004**. These cannot be
  "phases"; they are a fork into an enterprise SaaS product.

**Recommendation:** Keep forge-os local-first. Cherry-pick the additive items into the
native roadmap (Phase 11 already targets one of them). If the enterprise vision is real,
build it as a **separate `aegis` service that embeds forge-os as its core library** —
forge-os's strict layer architecture (core never imports cli/adapters) makes it embeddable.
Do **not** mutate forge-os into Aegis.

## The load-bearing conflict

| Aegis mandates | forge-os today | Verdict |
|---|---|---|
| PostgreSQL, Redis, OpenSearch, MinIO, Neo4j | `state.json` + local SQLite event store, in-process bus | **Violates L004** (no DB server / network service / cloud API) |
| Kubernetes, Helm, Terraform deploy | ships as a `pipx` CLI | Violates ADR-001 (local-first) |
| FastAPI REST gateway as primary surface | Typer CLI as primary surface | Different product shape |
| Multi-tenant RBAC/ABAC, JWT/OAuth2 | single-user, no auth code | Meaningless for a local CLI |
| OpenTelemetry/Prometheus/Grafana/Loki | local `daemon/metrics.json` + `events.jsonl` | Server-tier observability |
| React web UI | CLI + Rich terminal output | Major scope/identity shift |

forge-os runtime deps are **exactly four**: `pydantic, pyyaml, rich, typer`. Everything
else (anthropic, httpx, aiohttp) is an **optional** extra. That zero-server property is the
product's whole identity.

## Full phase × sprint mapping

Legend: ✅ shipped · 🟡 partial · ➕ new (local-first OK) · ⛔ conflicts with local-first

### Aegis Phase 1 — Core Infrastructure
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 1.1 Inter-module comm protocol | `events/bus.py` in-process bus, `events/model.py`, `hooks/registry.py`, KernelAdapter as the module boundary | ✅ (distributed/gRPC framing ⛔) |
| 1.2 Centralized state mgmt | `core/state_manager.py` (sole writer, atomic, event-append) + `events/store.py` (SQLite event sourcing, dual-write) | ✅ (shared-DB framing ⛔) |
| 1.3 Error handling / resilience | typed exceptions (`StateError`), hook timeout+failure isolation, fail-closed security gate; retries/backoff only in daemon | 🟡 (backoff partial) |
| 1.x "15 core modules" initial | Agent Runtime ✅, Task Scheduler ✅(daemon), Event Bus ✅, Memory ✅, Artifact ✅, Security ✅, Audit ✅; Workflow Engine 🟡(stage machine, not generic DAG), Plugin Mgr 🟡, Tool Registry 🟡, Governance 🟡(gates), Cost 🟡(per-run token/cost), Knowledge ⛔, Evaluation ➕, Deployment ➕ | mixed |

### Aegis Phase 2 — Modularity & Extensibility
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 2.1 Plugin lifecycle | adapter `registry.py` (priority + optional-dep guards), ACP registry adapter (binary/npx/uvx install). No generic activate/deactivate/uninstall/sandbox | 🟡 → ➕ **= native Phase 11 target** |
| 2.2 Model provider abstraction | `adapters/` (`IKernelAdapter`/`KernelAdapter`), 7 working adapters + 2 placeholders. Spawn-centric, not `generate/stream/embeddings/tools` | 🟡 → ➕ (Ollama/vLLM/LM Studio are *local* — compatible; embeddings iface is new) |
| 2.3 Dynamic config / flags / multi-tenancy | `config/` + `config.yaml` + `features.*` flags (observer gated) | ✅ flags; multi-tenancy ⛔ |
| 2.x Agent system (11 roles) | 12 stage personas + 4 cross-stage personas already (`agents/personas`) | ✅ |

### Aegis Phase 3 — Security & Governance
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 3.1 RBAC/ABAC | none (single-user) | ⛔ (presumes multi-user server) |
| 3.2 Audit logging + Loki/Prometheus | `security-audit.jsonl` (authoritative) + `events.jsonl` + SQLite store | ✅ audit; Loki/Prom ⛔ |
| 3.3 Governance layer | `gates/` (GateCoordinator) + `SecurityEnforcer` + human-approval for high-risk = de-facto governance | 🟡 (works; no formal "layer") |

### Aegis Phase 4 — Data & Intelligence
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 4.1 Knowledge graph (Neo4j) | none | ⛔ Neo4j; ➕ a sqlite "KG-lite" would be compatible |
| 4.2 Memory optimization | `memory/` (lessons, reflections, global_store, project_profiles) + `context/` (pruner mtime cache, lazy, budget) | ✅ (configurable eviction = ➕) |
| 4.3 Artifact mgmt / data flow | `context/registry.py` artifact registry + ADG (stale propagation, JSON persist) | ✅ (versioning/metadata/search = ➕) |
| 4.x SDLC module | **this is the core product** — requirements/arch/sprint/review/test/deploy personas exist | ✅ |
| 4.x ADLC module (dataset/prompt/model/eval registries) | none | ➕ **most novel additive area** (local file/sqlite registries) |

### Aegis Phase 5 — Testing & Deployment
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 5.1 E2E testing framework | `tests/integration/` (lifecycle happy/failure, adapter-swap) — **delivered in Phase 12** | ✅ |
| 5.2 Advanced CI/CD (Actions/Docker/Helm/K8s/Terraform) | `.github/workflows/ci.yml` + Docker-first validation | ✅ CI+Docker; Helm/K8s/Terraform ⛔ |

### Aegis Phase 6 — Performance & Monitoring
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 6.1 Perf benchmarking | `tests/perf/` NFR latency benchmarks + baseline doc — **delivered in Phase 12 (P12.05–08)** | ✅ |
| 6.2 Advanced observability (OTel/Prom/Grafana/Loki) | `daemon/metrics.json` local metrics + events | 🟡 local; server stack ⛔ |

### Aegis Phase 7 — UI/UX
| Aegis sprint | forge-os reality | Bucket |
|---|---|---|
| 7.1 React UI prototype | none (CLI + Rich) | ➕ but major identity shift |

## What's genuinely worth pulling in (additive, local-first-safe)

These could become native forge-os phases without touching the zero-server property:

1. **Generic plugin/extension lifecycle** (Aegis 2.1) — *already the native Phase 11 scope.*
   The roadmaps converge here. This is the cleanest "do it next" item.
2. **Broader model-provider abstraction** (Aegis 2.2) — add a `generate/stream/embeddings`
   surface and **local** providers (Ollama, vLLM, LM Studio). Skip the cloud-SDK breadth
   unless asked.
3. **ADLC registries** (Aegis 4.x) — dataset/prompt/model/eval tracking as local
   files/sqlite. The single most novel capability gap; complements the existing SDLC core.
4. **Configurable memory eviction + artifact versioning/metadata** (Aegis 4.2/4.3) —
   incremental hardening of modules that already exist.
5. **Knowledge-graph-lite** (Aegis 4.1) — *only* if backed by local sqlite, never Neo4j.

## What to refuse as forge-os phases (would break the product)

Postgres/Redis/OpenSearch/MinIO/Neo4j · Kubernetes/Helm/Terraform · FastAPI as primary
surface · multi-tenant RBAC/ABAC/JWT/OAuth2 · OTel/Prometheus/Grafana/Loki stack · web UI.

If the owner wants these, the right architecture is a **separate `aegis` repo**: a FastAPI
service + Postgres + K8s that **imports `forge_os` as its orchestration core/library**. The
core stays local-first and dependency-light; the enterprise tier wraps it. This is exactly
what ADR-001's adapter boundary was designed to allow.

## Recommended next step (owner's call)

- **Path A (recommended):** Proceed with **native Phase 11 (extension/plugin system)** —
  it *is* Aegis Sprint 2.1, so we satisfy the highest-value Aegis item while staying on the
  committed roadmap. Then optionally slot ADLC registries + provider-abstraction breadth as
  Phase 12.5 / 13.
- **Path B:** Spin up a separate `aegis` service repo that embeds forge-os, leaving
  forge-os untouched. Larger effort; only if the enterprise/SaaS target is real.
- **Path C:** Full pivot — rewrite forge-os into Aegis. **Not recommended**: discards the
  local-first identity, violates L004/ADR-001, and rebuilds ~60% that already works.
