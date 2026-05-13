## CocoIndex for Forge OS: Deep Research Report

---

### 1. Executive Summary

**CocoIndex** (cocoindex-io/cocoindex) is a 9.7k★ open-source **incremental data transformation engine** purpose-built for AI workloads. It is specifically marketed as a tool for **"long‑horizon agents"** — keeping their context continuously fresh by recomputing only the delta (Δ) on every source or logic change. It is built on a **Rust core** (25.4% of the codebase) with a **Python SDK** (74.1%), has reached **v1.0.3** (197 releases, 77 contributors), and supports Python 3.14's free‑threaded mode for true GIL‑free parallelism.

For Forge OS, CocoIndex directly addresses two of the hardest technical challenges identified in the design: **incremental context indexing** (keeping the ADG and LKG continuously fresh without full recomputation) and **code‑intelligent chunking** (Tree‑sitter based splitting that respects semantic boundaries). It is complementary to the graph‑based memory tools already surveyed (Neo4j MCP, Cuba‑Memorys, Kioku‑Lite) and provides the **incremental indexing pipeline layer** that none of those tools offer.

---

### 2. What CocoIndex Is

#### 2.1 Core Mental Model: Target = F(Source)

CocoIndex treats data pipelines like spreadsheets or React components: developers **declare target states** (what should exist in a database or index) as a function of source data, and the engine automatically computes the delta — inserting new rows, updating changed rows, and removing deleted rows — without any imperative ETL logic.

```python
@coco.fn(memo=True)  # ← cached by hash(input) + hash(code)
async def index_file(file, table):
    for chunk in RecursiveSplitter().split(await file.read_text()):
        table.declare_row(text=chunk.text, embedding=embed(chunk.text))

@coco.fn
async def main(src):
    table = await postgres.mount_table_target(PG, table_name="docs")
    table.declare_vector_index(column="embedding")
    await coco.mount_each(index_file, localfs.walk_dir(src).items(), table)
```

When this runs, only files that have changed since the last execution are re‑chunked and re‑embedded.

#### 2.2 Architecture: Python Frontend + Rust Engine

CocoIndex uses a **layered architecture** with a developer‑friendly Python SDK backed by a high‑performance Rust execution engine that handles concurrency, change detection, and state persistence. The engine uses **LMDB** for fingerprinting and includes a sophisticated **memoization system** with TTL support and UUID‑based storage management.

The **flow analysis and execution engine** uses a hierarchical scope system to manage values as they flow through nested operations, with automatic caching that avoids recomputing expensive operations. When the user code logic changes, the engine detects the change via **AST fingerprinting** and triggers re‑execution of only the affected branches.

#### 2.3 Production Maturity

| Metric | Value |
|--------|-------|
| Stars | 9,700 |
| Releases | 197 (v1.0.3 as of May 5, 2026) |
| Contributors | 77 |
| License | Apache 2.0 |
| Languages | Python 74.1%, Rust 25.4% |
| Supported Python | 3.14 free‑threaded mode (no GIL) |
| Examples | 20+ (code embedding, text embedding, knowledge graph, conversation-to-knowledge, PDF, audio) |
| Community | Discord, X, `good first issues` label, contributing guide |

---

### 3. Features Directly Relevant to Forge OS's Indexing & Pruning

#### 3.1 Incremental Processing — The Δ Engine

This is the single most architecturally relevant feature for Forge OS's context pruning system. CocoIndex tracks:

- **Source data changes**: file modification times, added/deleted files (via metadata check comparing `modified_time` from the backend, skipping if unchanged).
- **Logic changes**: AST fingerprinting of Python transformation code — if you change how chunks are split or embeddings are generated, only the affected records are recomputed.
- **Dependency changes**: if one processing component depends on another, changes propagate through the dependency graph.

For Forge OS, this means that when a developer updates `architecture.md` (ADG node), the Context Pruner doesn't need to re‑index the entire project — CocoIndex recomputes only the embeddings and relevance scores for downstream artifacts affected by that change. This is precisely the **staleness detection** pattern Forge OS requires (FR‑ADG‑003).

#### 3.2 Tree‑Sitter Based Code Chunking

CocoIndex provides built‑in `RecursiveSplitter` that uses **Tree‑sitter parsers** across 20+ programming languages and Markdown. Unlike naive line‑based or character‑based splitters, it produces **semantically coherent chunks** that respect function boundaries, class definitions, and module‑level statements.

For Forge OS's Stage 6 (Build) and Stage 7 (Eval), this means:
- **Code‑intelligent context**: the Builder agent receives code snippets that are syntactically meaningful, not arbitrary line windows.
- **Precise retrieval**: when the Evaluator needs to check a specific test against a specific function, it can retrieve exactly that chunk rather than grepping through a flattened codebase.

There is already a community‑built **CocoIndex MCP server** for code development (`aanno/cocoindex-code-mcp-server`) that enables LLMs to retrieve relevant code snippets from large codebases efficiently and in real‑time, leveraging CocoIndex's incremental indexing, Tree‑sitter based chunking, and smart language‑specific embeddings.

#### 3.3 Memoization and Caching

Functions decorated with `@coco.fn(memo=True)` are automatically cached. The engine tracks:
- Input arguments.
- Function logic (via AST fingerprinting).
- Context dependencies.

If none change, execution is skipped entirely. This is exactly the pattern needed for Forge OS's **Lazy Context Builder** (FR‑LCB‑001‑004): when an agent requests a skill's full instructions, CocoIndex can ensure that if the skill hasn't changed and the input context hasn't changed, the cached version is served instantly without recomputation.

#### 3.4 Multi‑Backend Target Support

CocoIndex supports writing to **Postgres (pgvector)**, **LanceDB**, **Qdrant**, **TurboPuffer**, **local filesystem**, and **Kafka**. For Forge OS, this means the indexed context (chunks, embeddings, relevance scores) can be stored in whichever vector store is most appropriate for the deployment profile — embedded SQLite for `minimal`, LanceDB for `standard`, pgvector/Qdrant for `expert` team deployments.

#### 3.5 Live Mode for Streaming Sources

CocoIndex supports **live mode** for streaming sources like Kafka or local file watchers. For Forge OS's **Background Daemon** (FR‑BD‑001), this enables real‑time monitoring of the codebase: as files change during active development, CocoIndex's live updater (`FlowLiveUpdater`) incrementally re‑indexes only what changed and pushes fresh context to the Observer agent, without any batch‑style "stop the world and re‑index" operations.

---

### 4. Deep Mapping to Forge OS Components

| Forge OS Component | CocoIndex Contribution | Integration Pattern |
|-------------------|----------------------|-------------------|
| **Context Pruner (FR‑ADG‑002)** | Incremental re‑indexing of ADG artifacts; Tree‑sitter chunking for code; embedding generation for semantic relevance scoring | CocoIndex pipeline watches `pipeline/` directory; when any artifact changes, recomputes only downstream embeddings and relevance scores |
| **ADG Staleness Detection (FR‑ADG‑003)** | Logic change detection via AST fingerprinting; dependency‑aware cascade recomputation | When `architecture.md` changes, CocoIndex automatically marks `spec.md` and `task‑dag.md` chunks as needing re‑evaluation |
| **Lazy Context Builder (FR‑LCB‑001‑004)** | Memoized function execution; cached skill and lesson retrieval | Skill loading becomes `@coco.fn(memo=True)` — if skill code and input context haven't changed, cached skill prompt returned instantly |
| **Code‑Intelligent Context for Build/Eval** | Tree‑sitter `RecursiveSplitter`; language‑aware embedding | Builder agent queries CocoIndex‑backed MCP server for "function implementing authentication" → receives semantically coherent chunk, not arbitrary line window |
| **Background Daemon (FR‑BD‑001)** | Live mode with `FlowLiveUpdater`; file watcher for incremental updates | Daemon runs CocoIndex in live mode over `pipeline/` and `src/`; Observer agent receives continuously fresh index |
| **Token Economics Dashboard (FR‑TE‑001)** | Embedding generation cost tracking; chunk count metrics | CocoIndex tracks embedding API calls; Forge OS imports into token economics dashboard for cost attribution |
| **Knowledge Graph Maintenance** | `conversation_to_knowledge` example — extracts structured knowledge from unstructured conversations | Dreamer Agent pipeline: session transcripts → CocoIndex → structured knowledge nodes → LKG |

---

### 5. Comparison: CocoIndex vs. Current Forge OS Context Pruner Design

| Dimension | Forge OS Current Design | CocoIndex‑Enhanced Design |
|-----------|------------------------|---------------------------|
| **Change detection** | ADG‑based staleness flags (custom implementation needed) | LMDB‑backed fingerprinting + AST change detection (production‑ready, built‑in) |
| **Code chunking** | Not specified — likely naive line‑based or regex | Tree‑sitter syntax‑aware splitting across 20+ languages |
| **Embedding pipeline** | Needs custom integration | Built‑in local (SentenceTransformers) + cloud (LiteLLM, 100+ providers) with batching |
| **Caching** | Planned but not specified in detail | Automatic memoization with hash(input) + hash(code) + TTL + UUID storage |
| **Incremental update model** | "Re‑run pruner on each stage entry" | Δ‑only: changed files → changed chunks → changed embeddings → minimal recomputation |
| **Live mode** | Not specified | Built‑in file watcher and streaming source support |
| **Multi‑backend storage** | Designed for file‑based and graph DB | pgvector, LanceDB, Qdrant, TurboPuffer, local FS, Kafka — all pluggable |
| **Python integration** | Native Python | Native Python SDK (`pip install cocoindex`) |
| **Rust performance** | WASM module planned | Already Rust‑core, 352× faster than equivalent interpreted code on benchmarks |
| **MCP integration** | Designed | Community MCP server already exists (`cocoindex-code-mcp-server`) |

---

### 6. Integration Strategy for Forge OS

#### 6.1 Three‑Tier Integration Depth

**Tier 1 — Context Indexing Backend (Immediate, Phase 2‑3)**
- Use CocoIndex as the **incremental indexing engine** behind the Context Pruner. Instead of Forge OS building its own file‑watching, hashing, and delta‑detection logic, CocoIndex provides all of this out of the box.
- The Context Pruner's `prepare_context(stage)` function becomes a CocoIndex pipeline that watches `pipeline/`, `src/`, and `.forge/` directories, indexing artifacts and code with Tree‑sitter chunking.
- Relevance scoring (BM25 + graph‑distance) runs on top of CocoIndex's vector embeddings.

**Tier 2 — MCP Server for Agent Retrieval (Mid‑term, Phase 3‑4)**
- Deploy the CocoIndex code‑embedding MCP server (`cocoindex-code-mcp-server`) as a standard Forge OS tool.
- Stage 6 and 7 agents query it directly: "find the function that handles JWT validation" → returns precise, semantically chunked code.
- Forge OS's gate checker can verify that the retrieved chunk matches the expected test coverage.

**Tier 3 — Live Context for Daemon Mode (Advanced, Phase 5+)**
- Run CocoIndex in live mode inside the Background Daemon.
- As developers modify files during active sessions, CocoIndex's `FlowLiveUpdater` incrementally re‑indexes and pushes fresh relevance scores to the Observer agent.
- The Dreamer Agent's nightly consolidation can use CocoIndex's `conversation_to_knowledge` pipeline to extract structured lessons from session transcripts.

#### 6.2 Concrete Integration Code (How It Looks in Forge OS)

```python
# forge/_internal/indexing/cocoindex_pipeline.py
import cocoindex as coco
from cocoindex.connectors import localfs, postgres
from cocoindex.ops.text import RecursiveSplitter

@coco.fn(memo=True)
async def index_artifact(file, table):
    """Index a single pipeline artifact with metadata."""
    content = await file.read_text()
    chunks = RecursiveSplitter().split(content)
    for chunk in chunks:
        table.declare_row(
            text=chunk.text,
            embedding=embed(chunk.text),
            artifact_path=file.path,
            stage=extract_stage(file.path),
            depends_on=extract_dependencies(content),
        )

@coco.fn
async def main(pipeline_dir, src_dir):
    # Mount target: Forge OS's vector store (pgvector / LanceDB / SQLite-vec)
    table = await postgres.mount_table_target(PG, table_name="forge_context")

    # Declare vector index for semantic search
    table.declare_vector_index(column="embedding")

    # Index pipeline artifacts (ADG)
    await coco.mount_each(index_artifact, localfs.walk_dir(pipeline_dir).items(), table)

    # Index source code (Tree‑sitter chunking)
    await coco.mount_each(index_artifact, localfs.walk_dir(src_dir).items(), table)

# Run once; re‑run anytime — only the Δ is recomputed
app = coco.App(coco.AppConfig(name="forge-context"), main, pipeline_dir, src_dir)
app.update_blocking()
```

#### 6.3 Phase‑by‑Phase Implementation

| Phase | Action | Effort |
|-------|--------|--------|
| **Phase 2 (Agents & Gates)** | Replace naive file‑watching in Context Pruner with CocoIndex incremental pipeline for `pipeline/` artifacts | 1‑2 weeks |
| **Phase 3 (Memory)** | Use CocoIndex's Tree‑sitter chunking + embedding for code‑intelligent context retrieval in Stages 6‑7 | 1‑2 weeks |
| **Phase 4 (Skill Mining)** | CocoIndex `conversation_to_knowledge` pipeline for Dreamer Agent's daily session transcript analysis | 1 week |
| **Phase 5 (Daemon)** | Live mode CocoIndex inside Background Daemon for continuous incremental re‑indexing | 1 week |
| **Phase 6 (Enterprise Hardening)** | pgvector/LanceDB backend selection based on profile; embedding cost tracking for Token Economics Dashboard | 1 week |

---

### 7. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| CocoIndex requires Postgres (or similar) for vector storage | Medium | Use SQLite‑vec or LanceDB backend for `minimal` profile; Postgres only for `expert` |
| Embedding API costs for re‑indexing | Medium | Use local SentenceTransformers for `minimal`/`standard`; cloud APIs only when explicitly configured; CocoIndex's memoization ensures only deltas are re‑embedded |
| Dependency on CocoIndex's release cycle | Low | Apache 2.0 license; the Rust engine is stable at v1.0.3; community is active (commits as recent as May 12, 2026) |
| Learning curve for dataflow programming model | Low | Python‑native API; `<100 lines of code` for a production indexing pipeline; Forge OS wraps the complexity behind a simple `forge context index` command |

---

### 8. Verdict: Should Forge OS Adopt CocoIndex?

**Yes, as the incremental indexing backbone for the Context Pruner.** The reasons:

1. **Production‑ready at v1.0.3** with 9.7k stars, 197 releases, and a Rust core — not experimental.
2. **Directly solves the "stale context" problem** that Forge OS's ADG staleness detection is designed to address — without needing to build custom file‑watching, hashing, and delta‑detection logic.
3. **Tree‑sitter code chunking** provides the code‑intelligent context that makes Stages 6‑7 agents genuinely more precise.
4. **Memoization and AST change detection** enable the lazy context loading pattern without additional implementation.
5. **Existing MCP server** means Forge OS agents can query indexed code via standard protocol, not custom integration.
6. **Apache 2.0 license** — no licensing friction for inclusion in Forge OS.

The integration is **complementary, not duplicative**. CocoIndex provides the incremental indexing and chunking pipeline; Forge OS provides the ADG structure, gate enforcement, and governance layer on top. CocoIndex tells Forge OS **what changed and what's relevant**; Forge OS decides **what to inject into the agent's context** and **whether the result passes quality gates**.

---

### 9. Resources

- **GitHub**: https://github.com/cocoindex-io/cocoindex
- **Website**: https://cocoindex.io
- **DeepWiki Architecture**: https://deepwiki.com/cocoindex-io/cocoindex
- **Code Embedding Example**: https://github.com/cocoindex-io/cocoindex/tree/main/examples/code_embedding
- **CocoIndex MCP Server**: https://github.com/aanno/cocoindex-code-mcp-server
- **Quickstart**: https://cocoindex.io/docs/getting_started/quickstart
- **Claude Code Skill**: https://github.com/cocoindex-io/cocoindex-claude
