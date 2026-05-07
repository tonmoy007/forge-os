# Forge OS Security Baseline

Status: Phase 00 foundation decision.

Forge OS coordinates project lifecycle activity, file changes, tools, agents, hooks, and optional integrations. The default security posture must be conservative, local-first, auditable, and explicit.

## Security Principles

1. Local-first by default.
2. Least privilege for tools, agents, hooks, and plugins.
3. Human approval for destructive or high-risk operations.
4. No hidden state mutation.
5. No provider-specific dependency in core.
6. No indefinite execution; all executable gates/hooks/tools need timeouts.
7. Secrets must never be written to logs, generated docs, or state mirrors.
8. Optional integrations must fail closed for permissions and fail safe for orchestration state.
9. Every automated decision must be auditable.
10. State recovery must prefer preserving user data over automatic destructive repair.

## Trust Boundaries

| Boundary | Trusted? | Notes |
|---|---|---|
| Forge OS core | Trusted coordinator | Sole writer of canonical state |
| Project config | Partially trusted | Must be schema-validated |
| Hooks | Untrusted by default | Must run under policy and timeout |
| Agents | Untrusted by default | May propose changes; cannot directly own state |
| Provider adapters | Partially trusted | Normalize results; cannot bypass core policy |
| Plugins/extensions | Untrusted by default | Require manifest and permissions |
| OpenClaw | Optional external runtime | Cannot own Forge state or gate decisions |
| Human operator | Trusted for approvals | Approval should be logged for high-risk actions |

## State Ownership Rules

- `.forge/state.json` is canonical machine state.
- `pipeline/state.md` is a human-readable mirror, not the source of truth.
- Only Forge OS core state services may write canonical state.
- Agents, hooks, adapters, plugins, and channels must not write canonical state directly.
- State writes must be atomic.
- State-changing operations should append an auditable event.
- Recovery from partial writes must be deterministic and documented before implementation.

## Tool Permission Model

Tools should be represented as abstract capabilities before mapping to provider/runtime-specific tool names.

Initial tool capability categories:

| Capability | Default | Approval Needed? | Notes |
|---|---|---|---|
| `read_project_files` | Allow | No | Limited to project root unless configured |
| `write_project_files` | Deny for agents initially | Yes for broad writes | May be narrowed later by path policy |
| `read_outside_project` | Deny | Yes | High-risk privacy boundary |
| `write_outside_project` | Deny | Yes | High-risk/destructive |
| `run_safe_commands` | Deny until policy exists | Maybe | Must use allowlist and timeout |
| `run_arbitrary_commands` | Deny | Yes | High-risk |
| `network_access` | Deny for core tests | Yes | Optional integrations only |
| `manage_dependencies` | Deny | Yes | Can change execution surface |
| `delete_files` | Deny | Yes | Destructive |
| `modify_vcs_history` | Deny | Yes | Destructive/high-risk |
| `access_secrets` | Deny | Yes | Must never be logged |

## Human Approval Requirements

Human approval is required before:

1. Deleting files or directories.
2. Writing outside the project root.
3. Running arbitrary shell commands.
4. Installing dependencies.
5. Modifying version-control history.
6. Sending project content to a network service when not already configured.
7. Persisting global lessons derived from private project content.
8. Applying automatic backtrack/rework that changes existing artifacts.
9. Enabling plugins or extensions with new permissions.
10. Escalating an agent's tool profile.

## Audit Log Requirements

Security-relevant activity should be recorded in `.forge/security-audit.jsonl` once implemented.

Each audit entry should include:

- Schema version.
- Timestamp.
- Actor type: core, user, agent, hook, adapter, plugin.
- Actor id or name.
- Action.
- Target path/resource when applicable.
- Permission/capability used.
- Approval status.
- Decision: allowed, denied, warned, failed.
- Reason.
- Redaction marker if sensitive fields were omitted.

## Secret Handling

- Do not store API keys in `.forge/config.yaml` unless explicitly marked as references to environment variables.
- Prefer environment-variable references for provider credentials.
- Never print secrets in CLI output.
- Never write secrets to event logs, security audit logs, state mirrors, lessons, reflections, or generated reports.
- Redaction should happen before logging, not only at display time.

## Hook and External Command Policy

- Hooks are disabled by default until configured.
- Every hook command must have a timeout.
- Hook failure defaults to warning unless configured as blocking.
- Blocking hooks must fail safe: no state transition on failure.
- Executable gates must have timeout, working directory, and allowed command policy.
- Output capture should be size-limited to avoid oversized logs.

## Adapter Security Policy

- Core must communicate with adapters only through the `KernelAdapter` interface.
- Adapters must declare supported capabilities.
- Adapter default tools are intersected with Forge OS policy before use.
- Adapter failures must be normalized and logged.
- Provider-specific ids should be stored only in adapter metadata, not used as core identifiers.
- OpenClaw and other runtimes may execute agents, but Forge OS core owns gate decisions.

## Plugin and Extension Policy

Plugins are future-phase optional features. When implemented:

- Plugins require a manifest.
- Plugin permissions must be explicit.
- Plugin install/remove actions must be auditable.
- Plugins cannot write canonical state directly.
- Plugins cannot silently add provider credentials.
- Plugin failures must not corrupt Forge OS state.

## Secure Defaults for Phase 01+

- Start with no network use in core commands.
- Start with no arbitrary command execution.
- Generate local project files only.
- Refuse unsafe overwrite unless explicitly confirmed.
- Validate config before use.
- Keep `.forge/` files deterministic and human-inspectable where possible.

## Deferred Security Work

The following should be implemented in later phases:

- Formal permission evaluator.
- Approval prompt abstraction.
- Security audit log writer.
- Tool allowlist and denylist engine.
- Command sandbox policy.
- Plugin manifest validator.
- Secret scanner integration.
- Global memory privacy policy.
