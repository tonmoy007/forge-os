# ADR-007 — Security and Human Approval

Status: accepted

Date: Phase 00

## Context

Forge OS may eventually execute tools, run hooks, coordinate agents, install dependencies, send data to providers, and modify project artifacts. Unsafe defaults would create unacceptable risk.

## Decision

Forge OS uses conservative, least-privilege security defaults. Destructive and high-risk actions require human approval. Security-relevant decisions must be auditable.

Human approval is required before actions such as deleting files, writing outside the project root, running arbitrary commands, modifying version-control history, installing dependencies, escalating tool permissions, or sending project content to newly configured network services.

## Consequences

Positive:

- Users retain control over high-risk operations.
- Audits can explain automated decisions.
- Agents and plugins cannot silently escalate.
- Core can be used in sensitive environments.

Tradeoffs:

- Some workflows require explicit approval steps.
- Permission evaluation and audit logging add implementation complexity.

## Implementation Guidance

- Default to no arbitrary command execution.
- Default to no network use in core commands.
- All executable checks require timeouts.
- Secrets must be redacted before logging.
- Tool capabilities should be abstract and intersected with adapter/runtime capabilities.
