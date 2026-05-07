# Architecture Decision Records

Status: Phase 00 foundation baseline.

Formal ADRs are stored in `adr/`.

## Accepted ADRs

| ADR | Decision |
|---|---|
| `adr/ADR-001-runtime-and-packaging.md` | Use Python 3.11+, local Python package first, `pipx` later, standalone binaries later |
| `adr/ADR-002-local-first-core.md` | Core must be local-first and usable without network/provider services |
| `adr/ADR-003-open-formats.md` | Persist project data in open formats: YAML, JSON, JSONL, Markdown, GraphML |
| `adr/ADR-004-state-ownership-and-atomic-writes.md` | Forge OS core is the sole canonical state writer; writes must be atomic |
| `adr/ADR-005-kernel-adapter-boundary.md` | Core uses only the `KernelAdapter` interface for execution runtimes |
| `adr/ADR-006-optional-layers.md` | Daemon, channels, OpenClaw, plugins, and advanced automation are optional layers |
| `adr/ADR-007-security-and-human-approval.md` | Use conservative least-privilege defaults and require human approval for high-risk actions |
| `adr/ADR-008-openclaw-boundary.md` | OpenClaw integrates only through `OpenClawAdapter`; Forge OS remains source of truth |

## Decision Summary

- Runtime: Python 3.11+.
- Package import name: `forge_os`.
- Preferred CLI command: `forge`.
- Development package manager preference: `uv`, while preserving standard `pip` compatibility.
- Distribution: local Python package first, `pipx` later, standalone binary later.
- Core architecture: deterministic, local-first, state-owning orchestration engine.
- Adapter priority: `DummyAdapter`, `ClaudeCodeAdapter`, `CodexAdapter`, `OpenClawAdapter`, `OpenCodeAdapter`, `LocalLLMAdapter`, `HumanAdapter`.
- OpenClaw boundary: Forge OS Core → Kernel Adapter Interface → OpenClawAdapter → OpenClaw HTTP/WebSocket API → OpenClaw Gateway.

## Future ADR Candidates

Create additional ADRs when decisions change or when implementation reveals ambiguity around:

1. Schema version migration strategy.
2. Global memory privacy model.
3. Plugin signing/integrity requirements.
4. Standalone binary packaging approach.
5. Real-provider adapter credential handling details.
