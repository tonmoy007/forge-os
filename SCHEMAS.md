# Forge OS Schemas

Status: Phase 00 foundation baseline.

This document defines the initial open-format schema contract for Forge OS. Phase 01+ should mirror the relevant schemas into Pydantic models under `forge_os.schemas`.

## Schema Principles

1. Every persisted schema must include `schema_version`.
2. Machine-readable state is canonical where available.
3. Human-readable mirrors are generated from canonical machine state.
4. Unknown future-compatible fields should be preserved where safe.
5. Files must be deterministic enough for stable tests.
6. Timestamps should use RFC 3339 format with timezone.
7. IDs should be stable strings, not provider-specific opaque ids unless stored as metadata.
8. Secrets must not be persisted in logs, state mirrors, lessons, or reports.

## Format Decisions

| Data | Format | Path |
|---|---|---|
| Project config | YAML | `.forge/config.yaml` |
| Pipeline state | JSON | `.forge/state.json` |
| Lifecycle events | JSON Lines | `.forge/events.jsonl` |
| Session log | JSON Lines | `.forge/session-log.jsonl` |
| Security audit log | JSON Lines | `.forge/security-audit.jsonl` |
| Lessons | YAML | `.forge/lessons.yaml` |
| Reflections | Markdown with metadata or YAML sidecar | `.forge/reflections/` |
| Stage definitions | YAML | `pipeline/stages.yaml` |
| Gate definitions | YAML | `pipeline/gates.yaml` |
| Gate results | JSON or JSON Lines, phase-specific | `.forge/` or `pipeline/log/` |
| Artifact graph | GraphML | `pipeline/dependencies.graphml` |
| Architecture decisions | Markdown | `pipeline/decisions/` |
| Extension manifest | YAML | Plugin package or `.forge/extensions/` later |

## Common Types

### Status Values

Common status values should be lowercase strings.

Pipeline/stage statuses:

- `not_started`.
- `active`.
- `blocked`.
- `review_needed`.
- `complete`.
- `skipped`.

Gate statuses:

- `pass`.
- `fail`.
- `warn`.
- `skipped`.
- `error`.

Adapter statuses:

- `idle`.
- `running`.
- `succeeded`.
- `failed`.
- `cancelled`.
- `unknown`.

Lesson statuses:

- `proposed`.
- `accepted`.
- `deprecated`.
- `rejected`.

### Common Metadata

Most persisted records may include:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Version of the record schema |
| `id` | string | context-dependent | Stable Forge identifier |
| `created_at` | RFC 3339 string | context-dependent | Creation time |
| `updated_at` | RFC 3339 string | context-dependent | Last update time |
| `metadata` | object | no | Non-canonical integration details |

## Project Config Schema

Path: `.forge/config.yaml`.

Purpose: local project configuration.

Required fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Config schema version |
| `project.name` | string | yes | Human-readable project name |
| `project.root_policy` | string | no | Default `project_only` |
| `profile` | string | yes | `minimal`, `standard`, or custom profile id |
| `default_adapter` | string | no | Default adapter id, initially `dummy` |
| `adapters` | object | no | Adapter configuration by id |
| `security.profile` | string | no | Security profile id |
| `hooks.enabled` | boolean | no | Defaults false in early phases |
| `features` | object | no | Optional feature flags |

Initial constraints:

- Provider credentials should be environment variable references, not raw secrets.
- Unknown feature flags may be preserved but ignored.
- Missing optional sections should resolve to safe defaults.

## Pipeline State Schema

Path: `.forge/state.json`.

Purpose: canonical machine-readable project lifecycle state.

Required fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | State schema version |
| `project_id` | string | yes | Stable local project id |
| `profile` | string | yes | Active stage profile |
| `current_stage_id` | string or null | yes | Active stage |
| `stages` | array of stage state | yes | Per-stage state |
| `gates` | object | no | Latest gate results by gate/stage |
| `last_event_id` | string or null | no | Last appended event |
| `created_at` | RFC 3339 string | yes | State creation time |
| `updated_at` | RFC 3339 string | yes | Last state update |
| `metadata` | object | no | Non-canonical notes/integration data |

Stage state fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `stage_id` | string | yes | References stage definition |
| `status` | string | yes | Pipeline/stage status |
| `entered_at` | RFC 3339 string or null | no | When stage became active |
| `completed_at` | RFC 3339 string or null | no | When stage completed |
| `blocked_reason` | string or null | no | Human-readable block reason |
| `artifacts` | array of artifact ids | no | Artifacts associated with stage |

## Stage Definition Schema

Path: `pipeline/stages.yaml`.

Purpose: defines lifecycle stages for a profile.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Stage schema version |
| `profile` | string | yes | Profile id |
| `stages` | array | yes | Ordered stage definitions |

Stage definition fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | string | yes | Stable stage id |
| `name` | string | yes | Human-readable name |
| `description` | string | no | Stage purpose |
| `order` | integer | yes | Deterministic ordering |
| `required_artifacts` | array | no | Artifact ids or path patterns |
| `gate_ids` | array | no | Gates evaluated for this stage |
| `allowed_transitions` | array | no | Explicit next stage ids |
| `agent_personas` | array | no | Suggested personas, Phase 05+ |

Built-in profiles:

- Minimal: SRS, Build, Deploy.
- Standard: SRS, Product, Architecture, Spec, Plan, Build, Eval, Deploy, Monitor, Feedback, Resolve, Release.
- Expert: custom definitions.

## Gate Criterion Schema

Path: `pipeline/gates.yaml`.

Purpose: defines quality criteria for stages/transitions.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Gate schema version |
| `gates` | array | yes | Gate criteria |

Gate fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | string | yes | Stable gate id |
| `name` | string | yes | Human-readable name |
| `type` | string | yes | `required_file`, `pattern`, `command`, `manual`, later more |
| `stage_id` | string or null | no | Stage association |
| `severity` | string | yes | `blocking`, `warning`, `advisory` |
| `criteria` | object | yes | Type-specific criteria |
| `timeout_seconds` | integer or null | required for executable gates | Prevent hangs |
| `enabled` | boolean | no | Defaults true |

## Gate Result Schema

Purpose: normalized result of evaluating a gate.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Gate result schema version |
| `gate_id` | string | yes | Gate reference |
| `stage_id` | string or null | no | Stage reference |
| `status` | string | yes | pass, fail, warn, skipped, error |
| `summary` | string | yes | Human-readable outcome |
| `details` | object | no | Type-specific details |
| `started_at` | RFC 3339 string | yes | Evaluation start |
| `finished_at` | RFC 3339 string | yes | Evaluation end |
| `duration_ms` | integer | yes | Evaluation duration |
| `blocking` | boolean | yes | Whether result blocks progression |
| `metadata` | object | no | Non-canonical execution details |

## Lifecycle Event Schema

Path: `.forge/events.jsonl`.

Purpose: append-only lifecycle event log.

Fields per line:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Event schema version |
| `event_id` | string | yes | Stable event id |
| `event_type` | string | yes | Lifecycle event type |
| `timestamp` | RFC 3339 string | yes | Event time |
| `session_id` | string or null | no | Session reference |
| `stage_id` | string or null | no | Stage reference |
| `actor` | object | yes | Actor details |
| `payload` | object | no | Event-specific data |
| `redactions` | array | no | Redacted field descriptors |

Initial event types:

- `SessionStart`.
- `UserPromptSubmit`.
- `StageStarted`.
- `StageCompleted`.
- `GateStarted`.
- `GateCompleted`.
- `PreToolUse`.
- `PostToolUse`.
- `AdapterStarted`.
- `AdapterCompleted`.
- `Stop`.
- `SubagentStop`.
- `SessionEnd`.

## Agent Definition Schema

Purpose: defines an agent persona and expected output contract.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Agent schema version |
| `id` | string | yes | Persona id |
| `name` | string | yes | Human-readable name |
| `role` | string | yes | Persona role |
| `instructions` | string | yes | Role guidance |
| `allowed_tools` | array | no | Abstract tool capability ids |
| `output_contract` | object | no | Required output shape |
| `stage_ids` | array | no | Stages where persona applies |
| `metadata` | object | no | Non-canonical details |

## Kernel Adapter Schemas

### Agent Handle

Returned by `spawn_agent`.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Handle schema version |
| `handle_id` | string | yes | Forge-level handle id |
| `adapter_id` | string | yes | Adapter id |
| `provider_ref` | string or object | no | Provider-specific reference stored as metadata |
| `status` | string | yes | Adapter status |
| `capabilities` | array | no | Supported optional capabilities |
| `created_at` | RFC 3339 string | yes | Creation time |
| `metadata` | object | no | Additional adapter details |

### Event Response

Returned by `on_event`.

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Response schema version |
| `adapter_id` | string | yes | Adapter id |
| `status` | string | yes | succeeded, failed, skipped, etc. |
| `messages` | array | no | Normalized messages |
| `proposed_events` | array | no | Event proposals, not automatically persisted |
| `artifacts` | array | no | Proposed artifact references |
| `errors` | array | no | Normalized errors |
| `metadata` | object | no | Provider-specific metadata |

## Lesson Schema

Path: `.forge/lessons.yaml`.

Purpose: accepted and proposed project lessons.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Lesson file schema version |
| `lessons` | array | yes | Lesson records |

Lesson record fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | string | yes | Stable lesson id |
| `status` | string | yes | proposed, accepted, deprecated, rejected |
| `summary` | string | yes | Short lesson |
| `details` | string | no | Longer explanation |
| `source_event_id` | string or null | no | Origin event |
| `scope` | string | yes | project, global-candidate |
| `tags` | array | no | Search/filter tags |
| `created_at` | RFC 3339 string | yes | Creation time |
| `updated_at` | RFC 3339 string | yes | Last update |

## Reflection Schema

Path: `.forge/reflections/`.

Purpose: structured review/reflection records.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Reflection schema version |
| `id` | string | yes | Reflection id |
| `stage_id` | string or null | no | Related stage |
| `summary` | string | yes | Summary |
| `findings` | array | no | Findings or observations |
| `lesson_candidates` | array | no | Proposed lessons |
| `created_at` | RFC 3339 string | yes | Creation time |
| `metadata` | object | no | Extra context |

## Artifact Schema

Purpose: describes project artifacts tracked by Forge OS.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Artifact schema version |
| `artifact_id` | string | yes | Stable artifact id |
| `path` | string | yes | Project-relative path |
| `kind` | string | yes | srs, spec, code, test, config, doc, etc. |
| `stage_id` | string or null | no | Owning/producing stage |
| `checksum` | string or null | no | Optional content hash |
| `updated_at` | RFC 3339 string | no | Last observed update |
| `metadata` | object | no | Additional data |

## Artifact Dependency Graph Schema

Path: `pipeline/dependencies.graphml`.

Purpose: tracks artifact dependencies and staleness.

Node attributes:

| Attribute | Type | Notes |
|---|---|---|
| `artifact_id` | string | Stable id |
| `path` | string | Project-relative path |
| `kind` | string | Artifact kind |
| `stage_id` | string | Related stage if any |
| `checksum` | string | Optional content hash |
| `staleness` | string | fresh, stale, unknown |

Edge attributes:

| Attribute | Type | Notes |
|---|---|---|
| `relationship` | string | depends_on, derives_from, validates, supersedes |
| `created_at` | string | RFC 3339 timestamp |
| `metadata` | string/object encoded safely | Implementation-specific |

## Backtrack Ticket Schema

Purpose: tracks rework/backtracking requests.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Ticket schema version |
| `ticket_id` | string | yes | Stable ticket id |
| `status` | string | yes | open, approved, in_progress, resolved, rejected |
| `reason` | string | yes | Why backtrack is needed |
| `source_stage_id` | string | yes | Where issue was found |
| `target_stage_id` | string | yes | Stage to revisit |
| `affected_artifacts` | array | no | Artifact ids |
| `requires_approval` | boolean | yes | Usually true |
| `created_at` | RFC 3339 string | yes | Creation time |
| `resolved_at` | RFC 3339 string or null | no | Resolution time |

## Tool and Security Profile Schema

Purpose: defines allowed capabilities and approval requirements.

Fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Security schema version |
| `profile_id` | string | yes | Security profile id |
| `default_policy` | string | yes | allow, deny, prompt |
| `capabilities` | array | yes | Capability rules |
| `audit_enabled` | boolean | yes | Defaults true |

Capability rule fields:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `capability` | string | yes | Abstract capability id |
| `policy` | string | yes | allow, deny, prompt |
| `scope` | object | no | Path/resource scope |
| `requires_approval` | boolean | yes | Explicit approval requirement |
| `timeout_seconds` | integer or null | no | Required for execution capabilities |

## Security Audit Entry Schema

Path: `.forge/security-audit.jsonl`.

Fields per line:

| Field | Type | Required | Notes |
|---|---|---:|---|
| `schema_version` | string | yes | Audit schema version |
| `audit_id` | string | yes | Stable audit id |
| `timestamp` | RFC 3339 string | yes | Decision/action time |
| `actor` | object | yes | Actor details |
| `action` | string | yes | Action attempted |
| `target` | string or object | no | Path/resource |
| `capability` | string | no | Capability used/requested |
| `decision` | string | yes | allowed, denied, warned, failed |
| `approval` | object | no | Approval metadata |
| `reason` | string | no | Explanation |
| `redactions` | array | no | Redacted sensitive fields |

## Channel Message Schema Later

Phase: 11.

Purpose: normalized messages from Slack/Discord/Linear/GitHub/etc.

Minimum planned fields:

- `schema_version`.
- `message_id`.
- `channel_id`.
- `sender`.
- `timestamp`.
- `intent`.
- `payload`.
- `approval_context`.

## Extension Manifest Schema Later

Phase: 11.

Purpose: describes plugin metadata, permissions, hooks, and compatibility.

Minimum planned fields:

- `schema_version`.
- `extension_id`.
- `name`.
- `version`.
- `forge_os_version_range`.
- `permissions`.
- `hooks`.
- `entry_points`.
- `signature` or integrity metadata, later.

## Phase 01 Schema Implementation Guidance

Phase 01 should implement only the schema models required for project initialization and status:

1. Project config.
2. Pipeline state skeleton.
3. Stage definition skeleton.
4. Gate definition skeleton if default gate files are emitted.
5. Common status enums or literals as needed.

Future schemas may remain documented until their implementation phase.
