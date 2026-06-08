"""
forge.kernel.harness
====================

The kernel comparison harness — the apparatus that "stages the race" between
Forge OS's kernel adapters.

You built five contestants, all behind the same `IKernelAdapter` contract:

    claude_adapter.py       -> raw Anthropic Messages API
    claude_sdk_adapter.py   -> Claude Agent SDK
    opencode_adapter.py     -> `opencode serve` (HTTP+SSE)
    human_adapter.py        -> a person at a terminal
    codex_adapter.py        -> `codex app-server` (JSON-RPC)

This module runs the SAME persona + context + tools through each of them and
produces an apples-to-apples comparison: latency (wall-clock, time-to-first-
token, time-to-completion), multi-turn tool-loop overhead, token/volume
efficiency, error/recovery behavior, and cross-kernel output drift — with
repeats and variance so a one-off fluke doesn't masquerade as a result.

The fairness principle (why there is a *stub* judge)
----------------------------------------------------
A kernel adapter's `spawn_agent()` is an async generator that yields
ToolUseProposal at the Proposal boundary and *pauses* until the orchestrator
feeds back a ToolResult via `asend()`. In production that ToolResult comes from
Forge's Validator + Executor — which is variable (real I/O), side-effecting, and
slow. If the harness used the real Executor, the benchmark would measure
"who-runs-the-tool," not "which kernel is faster/cleaner." That is exactly the
distinction your Claude-SDK and OpenCode adapters went to great lengths to
preserve.

So the harness answers proposals with a deterministic **ProposalJudge**: the
same proposed `Bash` always gets the same canned stdout, regardless of kernel.
Tool outcomes are held constant; the kernel is the only moving part. The judge
is pluggable — pass a Forge-backed judge if you specifically want an
*integration* benchmark — but the default is a controlled constant.

What it measures (per run, then aggregated over repeats)
--------------------------------------------------------
- wall_clock_s              total time the agent loop took
- time_to_first_event_s     first normalized event after spawn
- time_to_first_token_s     first TEXT_DELTA (None if the kernel never streams text)
- time_to_completion_s      AGENT_COMPLETED/last event
- num_proposals             tool-loop iterations (each costs one asend round-trip)
- tool_loop_overhead_s      summed kernel resume latency after each ToolResult
- text_chars / thinking_chars   output-volume proxies
- reported_input/output_tokens  picked up IF the kernel surfaces usage in an
                                 event payload (Codex tokenUsage, Claude usage, ...)
- server_tool_execs         count of kernel-executed tools (web_search, etc.)
- status                    COMPLETED | FAILED | TIMEOUT | ERROR
- final_output              accumulated agent text (used for drift)

Fairness controls
-----------------
- Same persona, same context, same tools, same judge across all kernels.
- Runs are SEQUENTIAL by default; parallel runs contend for CPU/network and
  pollute latency numbers.
- Optional `judge_latency_s` simulates a fixed Validator cost applied uniformly
  to every kernel, so it never biases one.
- Each kernel's `get_capabilities()` is captured so the report can contextualize
  results (the Human kernel has no streaming; Codex has native_approval_boundary;
  only kernels reporting `deterministic_output=True` are expected to be stable
  across repeats).

Dependencies
------------
    # stdlib only: asyncio, time, json, statistics, difflib, dataclasses.
    # No pip install. Bring your own (real) adapters; MockAdapter is included so
    # the harness itself is runnable/testable without any kernel.

Usage
-----
    from forge.kernel.harness import compare, BenchTask, ScriptedJudge
    from forge.kernel.claude import ClaudeAdapter
    from forge.kernel.codex import CodexAdapter

    report = await compare(
        kernels={"claude": ClaudeAdapter(), "codex": CodexAdapter()},
        persona=my_persona,
        tasks=[BenchTask("greet", "Sketch one domain event for a greeting service.")],
        judge=ScriptedJudge({"Bash": ("ok\\n", False), "Write": ("written", False)}),
        repeats=3,
    )
    print(report.to_markdown())
    report.write("/tmp/run")     # -> /tmp/run.md + /tmp/run.json
"""

from __future__ import annotations

import asyncio
import difflib
import json
import statistics
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from forge_os.kernel.types import (
    AgentPersona,
    EventKind,
    IKernelAdapter,
    KernelCapabilities,
    NormalizedEvent,
    ToolResult,
    ToolUseProposal,
)

# Event-payload keys a kernel might use to surface token usage. The harness
# reads these opportunistically; it never invents numbers.
_USAGE_KEYS = ("usage", "token_usage", "tokenUsage", "tokens")


# ============================================================================
# Section 2 — Bench task + the deterministic judge
# ============================================================================

@dataclass
class BenchTask:
    """One task run identically across every kernel."""
    task_id: str
    context: str
    tools: list[str | None] = None
    # Optional reference output for scoring/conformance (not required).
    expected_contains: list[str] = field(default_factory=list)
    notes: str = ""


class ProposalJudge:
    """Answers ToolUseProposals so the kernel can continue. Subclass to plug in
    a real Forge-backed Validator/Executor for an integration benchmark."""

    def decide(self, proposal: ToolUseProposal, task: BenchTask) -> ToolResult:
        raise NotImplementedError


class AutoApproveJudge(ProposalJudge):
    """Approve everything with a single canned, content-free result.

    The simplest possible constant: every proposal, every kernel, same answer.
    """

    def __init__(self, content: Any = '{"ok": true}') -> None:
        self._content = content

    def decide(self, proposal, task):
        return ToolResult(tool_use_id=proposal.tool_use_id,
                          content=self._content, is_error=False)


class ScriptedJudge(ProposalJudge):
    """Map an abstract tool name to a fixed (content, is_error) outcome.

    This is the recommended judge: it keeps tool *outcomes* identical across
    kernels (a `Bash` proposal always yields the same stdout) so the only
    variable is the kernel. Unknown tools fall back to `default`.
    """

    def __init__(
        self,
        script: dict[str, tuple[Any, bool]],
        default: tuple[Any, bool] = ('{"ok": true}', False),
    ) -> None:
        self._script = dict(script)
        self._default = default

    def decide(self, proposal, task):
        content, is_error = self._script.get(proposal.abstract_tool, self._default)
        return ToolResult(tool_use_id=proposal.tool_use_id,
                          content=content, is_error=is_error)


# ============================================================================
# Section 3 — Per-run result + recorder
# ============================================================================

class RunStatus(str, Enum):  # noqa: UP042
    COMPLETED = "completed"   # finished cleanly, no AGENT_FAILED
    FAILED    = "failed"      # kernel emitted AGENT_FAILED (graceful failure)
    TIMEOUT   = "timeout"     # exceeded the per-run timeout
    ERROR     = "error"       # exception escaped the adapter / harness


@dataclass
class RunResult:
    kernel_id: str
    task_id: str
    run_index: int
    status: RunStatus
    wall_clock_s: float
    time_to_first_event_s: float | None = None
    time_to_first_token_s: float | None = None
    time_to_completion_s: float | None = None
    num_proposals: int = 0
    tool_loop_overhead_s: float = 0.0
    text_chars: int = 0
    thinking_chars: int = 0
    reported_input_tokens: int | None = None
    reported_output_tokens: int | None = None
    server_tool_execs: int = 0
    event_counts: dict[str, int] = field(default_factory=dict)
    final_output: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == RunStatus.COMPLETED


class _Recorder:
    """Accumulates timing + counts while a run is in flight."""

    def __init__(self, kernel_id: str, task_id: str, run_index: int) -> None:
        self.kernel_id = kernel_id
        self.task_id = task_id
        self.run_index = run_index
        self._t0 = 0.0
        self._first_event_t: float | None = None
        self._first_token_t: float | None = None
        self._completion_t: float | None = None
        self._pending_send_t: float | None = None
        self.num_proposals = 0
        self.tool_loop_overhead_s = 0.0
        self.text_chars = 0
        self.thinking_chars = 0
        self.in_tokens: int | None = None
        self.out_tokens: int | None = None
        self.server_tool_execs = 0
        self.event_counts: dict[str, int] = {}
        self.text_parts: list[str] = []
        self.agent_failed = False

    def start(self) -> None:
        self._t0 = time.perf_counter()

    def mark_send(self) -> None:
        # Called right before asend(ToolResult); the next event's arrival time
        # minus this is the kernel's resume (tool-loop) latency.
        self._pending_send_t = time.perf_counter()

    def observe(self, event: NormalizedEvent) -> None:
        now = time.perf_counter()
        if self._first_event_t is None:
            self._first_event_t = now
        if self._pending_send_t is not None:
            self.tool_loop_overhead_s += now - self._pending_send_t
            self._pending_send_t = None

        kind = event.kind
        key = kind.value if isinstance(kind, Enum) else str(kind)
        self.event_counts[key] = self.event_counts.get(key, 0) + 1

        if kind == EventKind.TEXT_DELTA:
            text = str(event.payload.get("text", ""))
            self.text_chars += len(text)
            self.text_parts.append(text)
            if self._first_token_t is None and text:
                self._first_token_t = now
        elif kind == EventKind.THINKING_DELTA:
            self.thinking_chars += len(str(event.payload.get("text", "")))
        elif kind == EventKind.TOOL_USE_PROPOSED:
            self.num_proposals += 1
        elif kind == EventKind.SERVER_TOOL_EXECUTED:
            self.server_tool_execs += 1
        elif kind == EventKind.AGENT_FAILED:
            self.agent_failed = True
            self._completion_t = now
        elif kind == EventKind.AGENT_COMPLETED:
            self._completion_t = now

        self._absorb_usage(event.payload)

    def _absorb_usage(self, payload: dict[str, Any]) -> None:
        for k in _USAGE_KEYS:
            if k in payload:
                u = payload[k]
                if isinstance(u, dict):
                    self.in_tokens = _first_int(u, ("input_tokens", "prompt_tokens",
                                                     "input", "in")) or self.in_tokens
                    self.out_tokens = _first_int(u, ("output_tokens", "completion_tokens",
                                                      "output", "out")) or self.out_tokens
                elif isinstance(u, int):
                    self.out_tokens = u

    def finish(self, status: RunStatus, error: str | None = None) -> RunResult:
        end = time.perf_counter()
        if status == RunStatus.COMPLETED and self.agent_failed:
            status = RunStatus.FAILED
        def rel(t: float | None) -> float | None:
            return (t - self._t0) if t is not None else None
        return RunResult(
            kernel_id=self.kernel_id,
            task_id=self.task_id,
            run_index=self.run_index,
            status=status,
            wall_clock_s=end - self._t0,
            time_to_first_event_s=rel(self._first_event_t),
            time_to_first_token_s=rel(self._first_token_t),
            time_to_completion_s=rel(self._completion_t),
            num_proposals=self.num_proposals,
            tool_loop_overhead_s=self.tool_loop_overhead_s,
            text_chars=self.text_chars,
            thinking_chars=self.thinking_chars,
            reported_input_tokens=self.in_tokens,
            reported_output_tokens=self.out_tokens,
            server_tool_execs=self.server_tool_execs,
            event_counts=dict(self.event_counts),
            final_output="".join(self.text_parts).strip(),
            error=error,
        )


def _first_int(d: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, int):
            return v
    return None


# ============================================================================
# Section 4 — The single-run driver (the asend() loop)
# ============================================================================

async def run_kernel_once(
    adapter: IKernelAdapter,
    persona: AgentPersona,
    task: BenchTask,
    judge: ProposalJudge,
    *,
    run_index: int = 0,
    timeout_s: float = 120.0,
    judge_latency_s: float = 0.0,
) -> RunResult:
    """Drive one kernel through one task, honoring the Proposal boundary.

    This is the exact `asend()` handshake the adapters' own smoke tests use:
    yield a proposal, judge it, send back a ToolResult, continue.
    """
    kernel_id = _safe_kernel_id(adapter)
    rec = _Recorder(kernel_id, task.task_id, run_index)
    rec.start()
    agen = adapter.spawn_agent(
        persona=persona,
        context=task.context,
        tools=task.tools or persona.allowed_tools,
        aggregate_id=f"{kernel_id}-{task.task_id}-{run_index}",
    )

    async def _drive() -> None:
        pending: ToolUseProposal | None = None
        send: Any = None
        while True:
            if pending is not None:
                decision = judge.decide(pending, task)
                if judge_latency_s:
                    await asyncio.sleep(judge_latency_s)
                send = decision
                rec.mark_send()
            try:
                event = await agen.asend(send)
            except StopAsyncIteration:
                return
            send = None
            pending = None
            rec.observe(event)
            if isinstance(event, ToolUseProposal):
                pending = event

    try:
        await asyncio.wait_for(_drive(), timeout=timeout_s)
        return rec.finish(RunStatus.COMPLETED)
    except TimeoutError:
        await _aclose(agen)
        return rec.finish(RunStatus.TIMEOUT, error=f"timeout after {timeout_s}s")
    except Exception as exc:  # adapter raised; record and move on
        await _aclose(agen)
        return rec.finish(RunStatus.ERROR, error=f"{type(exc).__name__}: {exc}")


def _safe_kernel_id(adapter: IKernelAdapter) -> str:
    try:
        return adapter.get_capabilities().kernel_id
    except Exception:
        return adapter.__class__.__name__


async def _aclose(agen: AsyncIterator) -> None:
    try:
        await agen.aclose()  # type: ignore[attr-defined]
    except Exception:
        pass


# ============================================================================
# Section 5 — Aggregation across repeats
# ============================================================================

@dataclass
class MetricStats:
    mean: float | None = None
    median: float | None = None
    stdev: float | None = None
    min: float | None = None
    max: float | None = None
    n: int = 0


def _stats(values: list[float | None]) -> MetricStats:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return MetricStats(n=0)
    return MetricStats(
        mean=statistics.mean(vals),
        median=statistics.median(vals),
        stdev=(statistics.stdev(vals) if len(vals) > 1 else 0.0),
        min=min(vals),
        max=max(vals),
        n=len(vals),
    )


@dataclass
class KernelTaskSummary:
    kernel_id: str
    task_id: str
    runs: int
    successes: int
    success_rate: float
    statuses: dict[str, int]
    wall_clock_s: MetricStats
    time_to_first_token_s: MetricStats
    time_to_completion_s: MetricStats
    tool_loop_overhead_s: MetricStats
    num_proposals: MetricStats
    text_chars: MetricStats
    thinking_chars: MetricStats
    output_tokens: MetricStats
    errors: list[str]


def _summarize(kernel_id: str, task_id: str, runs: list[RunResult]) -> KernelTaskSummary:
    successes = sum(1 for r in runs if r.ok)
    statuses: dict[str, int] = {}
    for r in runs:
        statuses[r.status.value] = statuses.get(r.status.value, 0) + 1
    # Latency/quality stats computed over SUCCESSFUL runs only (a timed-out run
    # has a meaningless wall_clock for comparison). Counts use all runs.
    ok = [r for r in runs if r.ok]
    return KernelTaskSummary(
        kernel_id=kernel_id,
        task_id=task_id,
        runs=len(runs),
        successes=successes,
        success_rate=successes / len(runs) if runs else 0.0,
        statuses=statuses,
        wall_clock_s=_stats([r.wall_clock_s for r in ok]),
        time_to_first_token_s=_stats([r.time_to_first_token_s for r in ok]),
        time_to_completion_s=_stats([r.time_to_completion_s for r in ok]),
        tool_loop_overhead_s=_stats([r.tool_loop_overhead_s for r in ok]),
        num_proposals=_stats([float(r.num_proposals) for r in ok]),
        text_chars=_stats([float(r.text_chars) for r in ok]),
        thinking_chars=_stats([float(r.thinking_chars) for r in ok]),
        output_tokens=_stats([r.reported_output_tokens for r in ok]),
        errors=[r.error for r in runs if r.error],
    )


# ============================================================================
# Section 6 — Output-drift detection
# ============================================================================

@dataclass
class DriftReport:
    task_id: str
    outputs: dict[str, str]                       # kernel_id -> final output
    similarity: dict[str, dict[str, float]]       # pairwise lexical similarity
    min_pairwise: float | None
    high_drift_pairs: list[tuple[str, str, float]]
    json_conformant: dict[str, bool]              # kernel_id -> parsed as JSON
    missing_required: dict[str, list[str]]        # kernel_id -> missing fields
    expected_hits: dict[str, list[str]]           # kernel_id -> matched expected_contains


def compute_drift(
    task: BenchTask,
    first_success: dict[str, RunResult],
    persona: AgentPersona,
    threshold: float = 0.6,
) -> DriftReport:
    """Compare each kernel's final output for one task.

    Lexical similarity (difflib ratio) is a *proxy* for semantic drift — it
    flags divergence to inspect, not a semantic equivalence judgment. If the
    persona declares a JSON output_contract, we also report structural
    conformance and missing required fields.
    """
    outputs = {k: r.final_output for k, r in first_success.items()}
    kernels = list(outputs)

    sim: dict[str, dict[str, float]] = {a: {} for a in kernels}
    pair_scores: list[tuple[str, str, float]] = []
    for i, a in enumerate(kernels):
        for b in kernels[i + 1:]:
            ratio = difflib.SequenceMatcher(None, outputs[a], outputs[b]).ratio()
            sim[a][b] = ratio
            sim[b][a] = ratio
            pair_scores.append((a, b, ratio))
        sim[a][a] = 1.0

    min_pairwise = min((s for _, _, s in pair_scores), default=None)
    high_drift = sorted([p for p in pair_scores if p[2] < threshold], key=lambda p: p[2])

    required = []
    contract = persona.output_contract or {}
    if isinstance(contract, dict) and contract.get("type") == "object":
        required = list(contract.get("required", []))

    json_conformant: dict[str, bool] = {}
    missing_required: dict[str, list[str]] = {}
    for k, out in outputs.items():
        parsed = _try_json(out)
        json_conformant[k] = parsed is not None
        if parsed is not None and required:
            missing_required[k] = [f for f in required if f not in parsed]
        elif required:
            missing_required[k] = list(required)  # nothing parsed -> all missing

    expected_hits = {
        k: [s for s in task.expected_contains if s.lower() in out.lower()]
        for k, out in outputs.items()
    } if task.expected_contains else {}

    return DriftReport(
        task_id=task.task_id,
        outputs=outputs,
        similarity=sim,
        min_pairwise=min_pairwise,
        high_drift_pairs=high_drift,
        json_conformant=json_conformant,
        missing_required=missing_required,
        expected_hits=expected_hits,
    )


def _try_json(text: str) -> dict[str, Any | None]:
    text = text.strip()
    # Tolerate a fenced ```json block.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


# ============================================================================
# Section 7 — Orchestrator + report
# ============================================================================

@dataclass
class ComparisonReport:
    created_at: str
    persona_name: str
    repeats: int
    judge: str
    capabilities: dict[str, dict[str, Any]]            # kernel_id -> caps dict
    summaries: dict[str, dict[str, KernelTaskSummary]]  # task_id -> kernel_id -> summary
    drift: dict[str, DriftReport]                      # task_id -> drift
    raw_runs: list[RunResult]
    note: str = ""

    # ---- serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "persona_name": self.persona_name,
            "repeats": self.repeats,
            "judge": self.judge,
            "note": self.note,
            "capabilities": self.capabilities,
            "summaries": {
                t: {k: asdict(s) for k, s in ks.items()}
                for t, ks in self.summaries.items()
            },
            "drift": {t: asdict(d) for t, d in self.drift.items()},
            "raw_runs": [asdict(r) for r in self.raw_runs],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=_json_default)

    def write(self, path_stem: str) -> tuple[str, str]:
        md_path, json_path = f"{path_stem}.md", f"{path_stem}.json"
        with open(md_path, "w") as f:
            f.write(self.to_markdown())
        with open(json_path, "w") as f:
            f.write(self.to_json())
        return md_path, json_path

    # ---- human-facing report ----------------------------------------------

    def to_markdown(self) -> str:
        L: list[str] = []
        L.append("# Forge OS — Kernel Comparison Report")
        L.append("")
        L.append(f"- Generated: {self.created_at}")
        L.append(f"- Persona: `{self.persona_name}`")
        L.append(f"- Repeats per (kernel, task): {self.repeats}")
        L.append(f"- Judge: {self.judge}")
        if self.note:
            L.append(f"- Note: {self.note}")
        L.append("")

        # Capabilities table
        L.append("## Kernels under test")
        L.append("")
        L.append("| kernel | streaming | thinking | mcp (local/remote) | "
                 "native approval | deterministic |")
        L.append("|---|---|---|---|---|---|")
        for k, c in self.capabilities.items():
            L.append(
                f"| `{k}` | {_b(c.get('streaming'))} | {_b(c.get('extended_thinking'))} "
                f"| {_b(c.get('mcp_local'))}/{_b(c.get('mcp_remote'))} "
                f"| {_b(c.get('native_approval_boundary'))} "
                f"| {_b(c.get('deterministic_output'))} |"
            )
        L.append("")

        # Per-task metric tables + drift
        for task_id, ks in self.summaries.items():
            L.append(f"## Task: `{task_id}`")
            L.append("")
            L.append("| kernel | success | wall-clock s (mean±sd) | TTFT s | "
                     "completion s | #proposals | tool-loop s | text chars | "
                     "think chars | out tokens |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            for k, s in ks.items():
                L.append(
                    f"| `{k}` | {s.successes}/{s.runs} "
                    f"| {_ms(s.wall_clock_s)} "
                    f"| {_one(s.time_to_first_token_s)} "
                    f"| {_one(s.time_to_completion_s)} "
                    f"| {_one(s.num_proposals)} "
                    f"| {_one(s.tool_loop_overhead_s)} "
                    f"| {_one(s.text_chars)} "
                    f"| {_one(s.thinking_chars)} "
                    f"| {_one(s.output_tokens)} |"
                )
            L.append("")
            L.extend(self._leaderboard_lines(ks))
            L.append("")
            if task_id in self.drift:
                L.extend(self._drift_lines(self.drift[task_id]))
                L.append("")

        L.append("---")
        L.append("*Latency/quality stats are computed over successful runs only; "
                 "success counts use all runs. Token columns are blank unless the "
                 "kernel surfaced usage in an event payload. Drift similarity is a "
                 "lexical proxy (difflib), not a semantic equivalence judgment.*")
        return "\n".join(L)

    def _leaderboard_lines(self, ks: dict[str, KernelTaskSummary]) -> list[str]:
        usable = {k: s for k, s in ks.items() if s.wall_clock_s.n > 0}
        if len(usable) < 2:
            return []
        out = ["**Fastest (by metric):**", ""]
        picks = [
            ("wall-clock", lambda s: s.wall_clock_s.median),
            ("time-to-first-token", lambda s: s.time_to_first_token_s.median),
            ("tool-loop overhead", lambda s: s.tool_loop_overhead_s.median),
        ]
        for label, getter in picks:
            scored = [(k, getter(s)) for k, s in usable.items() if getter(s) is not None]
            if not scored:
                continue
            winner = min(scored, key=lambda kv: kv[1])
            out.append(f"- {label}: `{winner[0]}` ({_fmt(winner[1])} s)")
        return out

    def _drift_lines(self, d: DriftReport) -> list[str]:
        out = ["### Output drift", ""]
        kernels = list(d.outputs)
        if len(kernels) >= 2:
            header = "| | " + " | ".join(f"`{k}`" for k in kernels) + " |"
            sep = "|" + "---|" * (len(kernels) + 1)
            out += [header, sep]
            for a in kernels:
                row = [f"`{a}`"] + [_fmt(d.similarity.get(a, {}).get(b)) if a != b else "1.00"
                                    for b in kernels]
                out.append("| " + " | ".join(row) + " |")
            out.append("")
            if d.min_pairwise is not None:
                out.append(f"- Min pairwise similarity: **{_fmt(d.min_pairwise)}**")
            if d.high_drift_pairs:
                pairs = ", ".join(f"`{a}`↔`{b}` ({_fmt(s)})" for a, b, s in d.high_drift_pairs)
                out.append(f"- ⚠️ High-drift pairs (below threshold): {pairs}")
            else:
                out.append("- No high-drift pairs flagged.")
        if any(d.json_conformant.values()) or d.missing_required:
            conf = ", ".join(f"`{k}`={_b(v)}" for k, v in d.json_conformant.items())
            out.append(f"- JSON-conformant output: {conf}")
            for k, missing in d.missing_required.items():
                if missing:
                    out.append(f"  - `{k}` missing required fields: {missing}")
        if d.expected_hits:
            hits = ", ".join(f"`{k}`={len(v)}" for k, v in d.expected_hits.items())
            out.append(f"- expected_contains matches: {hits}")
        return out


async def compare(
    kernels: dict[str, IKernelAdapter],
    persona: AgentPersona,
    tasks: list[BenchTask],
    judge: ProposalJudge | None = None,
    *,
    repeats: int = 1,
    timeout_s: float = 120.0,
    judge_latency_s: float = 0.0,
    note: str = "",
) -> ComparisonReport:
    """Run every kernel through every task `repeats` times and build a report.

    Execution is sequential (one run at a time) so latency numbers are not
    polluted by contention.
    """
    judge = judge or ScriptedJudge({})
    raw_runs: list[RunResult] = []
    summaries: dict[str, dict[str, KernelTaskSummary]] = {}
    drift: dict[str, DriftReport] = {}

    # Capture capabilities up front for the report.
    capabilities: dict[str, dict[str, Any]] = {}
    for kid, adapter in kernels.items():
        try:
            capabilities[kid] = asdict(adapter.get_capabilities())
        except Exception as exc:  # pragma: no cover
            capabilities[kid] = {"kernel_id": kid, "error": repr(exc)}

    for task in tasks:
        summaries[task.task_id] = {}
        first_success: dict[str, RunResult] = {}
        for kid, adapter in kernels.items():
            runs: list[RunResult] = []
            for i in range(repeats):
                result = await run_kernel_once(
                    adapter, persona, task, judge,
                    run_index=i, timeout_s=timeout_s, judge_latency_s=judge_latency_s,
                )
                runs.append(result)
                raw_runs.append(result)
                if result.ok and kid not in first_success:
                    first_success[kid] = result
            summaries[task.task_id][kid] = _summarize(kid, task.task_id, runs)
        if first_success:
            drift[task.task_id] = compute_drift(task, first_success, persona)

    return ComparisonReport(
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        persona_name=persona.name,
        repeats=repeats,
        judge=judge.__class__.__name__,
        capabilities=capabilities,
        summaries=summaries,
        drift=drift,
        raw_runs=raw_runs,
        note=note,
    )


# ---- formatting helpers ----------------------------------------------------

def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f}"

def _one(s: MetricStats) -> str:
    return "—" if s.n == 0 or s.median is None else f"{s.median:.2f}"

def _ms(s: MetricStats) -> str:
    if s.n == 0 or s.mean is None:
        return "—"
    return f"{s.mean:.2f}±{(s.stdev or 0.0):.2f}"

def _b(v: Any) -> str:
    return "✓" if v else "·"

def _json_default(o: Any) -> Any:
    if isinstance(o, Enum):
        return o.value
    if hasattr(o, "__dict__"):
        return o.__dict__
    return str(o)


# ============================================================================
# Section 8 — MockAdapter (so the harness is runnable without any real kernel)
# ============================================================================

class MockAdapter(IKernelAdapter):
    """A scripted IKernelAdapter for testing the harness itself.

    Emits SESSION_STARTED -> THINKING_DELTA* -> TEXT_DELTA* -> [proposal] ->
    TEXT_DELTA* -> AGENT_COMPLETED, with configurable per-step latency, output
    text (to exercise drift), proposal count, optional reported token usage,
    and optional failure/timeout behavior.
    """

    def __init__(
        self,
        kernel_id: str,
        *,
        step_latency_s: float = 0.01,
        output_text: str = '{"event": "GreetingIssued"}',
        thinking_text: str = "considering the bounded context ",
        num_proposals: int = 1,
        report_tokens: tuple[int, int | None] = None,
        fail: bool = False,
        hang: bool = False,
        caps: KernelCapabilities | None = None,
    ) -> None:
        self._kernel_id = kernel_id
        self._lat = step_latency_s
        self._output = output_text
        self._thinking = thinking_text
        self._proposals = num_proposals
        self._tokens = report_tokens
        self._fail = fail
        self._hang = hang
        self._caps = caps or KernelCapabilities(
            kernel_id=kernel_id, streaming=True, extended_thinking=True,
            mcp_local=True, client_tools=["Read", "Write", "Bash"],
        )

    def get_capabilities(self) -> KernelCapabilities:
        return self._caps

    async def spawn_agent(self, persona, context, tools=None, aggregate_id=""):
        async def _sleep():
            if self._lat:
                await asyncio.sleep(self._lat)

        yield NormalizedEvent(EventKind.SESSION_STARTED, aggregate_id,
                              {"kernel": self._kernel_id})
        await _sleep()

        if self._hang:
            await asyncio.sleep(3600)  # force the harness timeout path

        for word in self._thinking.split():
            yield NormalizedEvent(EventKind.THINKING_DELTA, aggregate_id,
                                  {"text": word + " "})
            await _sleep()

        if self._fail:
            yield NormalizedEvent(EventKind.AGENT_FAILED, aggregate_id,
                                  {"error": "simulated kernel failure"})
            return

        # Stream half the output, then propose tools, then stream the rest.
        head = self._output[: len(self._output) // 2]
        tail = self._output[len(self._output) // 2:]
        for ch in _chunks(head, 6):
            yield NormalizedEvent(EventKind.TEXT_DELTA, aggregate_id, {"text": ch})
            await _sleep()

        for n in range(self._proposals):
            proposal = ToolUseProposal(
                kind=EventKind.TOOL_USE_PROPOSED,
                aggregate_id=aggregate_id,
                tool_use_id=f"mock-{n}",
                tool_name="shell",
                abstract_tool="Bash",
                inputs={"command": ["echo", "hi"]},
            )
            result: ToolResult | None = (yield proposal)
            await _sleep()
            # Echo a tiny acknowledgement of the judge's verdict as text.
            verdict = "declined" if (result and result.is_error) else "accepted"
            yield NormalizedEvent(EventKind.TEXT_DELTA, aggregate_id,
                                  {"text": f" [{verdict}] "})

        for ch in _chunks(tail, 6):
            yield NormalizedEvent(EventKind.TEXT_DELTA, aggregate_id, {"text": ch})
            await _sleep()

        payload: dict[str, Any] = {"status": "completed"}
        if self._tokens:
            payload["usage"] = {"input_tokens": self._tokens[0],
                                "output_tokens": self._tokens[1]}
        yield NormalizedEvent(EventKind.AGENT_COMPLETED, aggregate_id, payload)

    async def on_event(self, event):
        return None

    async def sync_memory(self, *args, **kwargs):
        return None


def _chunks(s: str, n: int):
    for i in range(0, len(s), n):
        yield s[i:i + n]


# ============================================================================
# Section 9 — Smoke test
# ============================================================================

async def _smoke_test() -> None:
    """Run with:  python comparison_harness.py --smoke

    Stages a race between several MOCK kernels (no real adapter required) so you
    can see the report format and verify the harness end-to-end.
    """
    persona = AgentPersona(
        name="event-storming",
        role="You are an event storming facilitator for Forge OS.",
        goal="Propose one domain event for a greeting service as JSON.",
        constraints=["Reply with a single JSON object.", "Use the propose tool."],
        allowed_tools=["Bash", "ProposeEvent"],
        output_contract={"type": "object", "required": ["event"]},
    )

    tasks = [
        BenchTask(
            task_id="greeting-event",
            context="Sketch one domain event for a greeting service. "
                    "Run a command if useful, then return JSON.",
            expected_contains=["event"],
        ),
    ]

    kernels: dict[str, IKernelAdapter] = {
        "mock-fast":   MockAdapter("mock-fast", step_latency_s=0.002,
                                   output_text='{"event": "GreetingIssued"}',
                                   report_tokens=(1200, 80)),
        "mock-slow":   MockAdapter("mock-slow", step_latency_s=0.02,
                                   output_text='{"event": "GreetingIssued"}',
                                   report_tokens=(1200, 95)),
        "mock-drifty": MockAdapter("mock-drifty", step_latency_s=0.006,
                                   output_text='{"domainEvent": "UserWasGreeted", "v": 2}'),
        "mock-flaky":  MockAdapter("mock-flaky", step_latency_s=0.004, fail=True),
    }

    judge = ScriptedJudge({"Bash": ("hello\n", False),
                           "ProposeEvent": ('{"ack": true}', False)})

    report = await compare(
        kernels, persona, tasks, judge,
        repeats=3, timeout_s=10.0,
        note="Illustrative run over MockAdapters — numbers are synthetic.",
    )

    print(report.to_markdown())
    md, js = report.write("comparison_report")
    print(f"\n[wrote] {md}\n[wrote] {js}")


if __name__ == "__main__":
    import sys
    if "--smoke" in sys.argv:
        asyncio.run(_smoke_test())
    else:
        print(
            "Forge OS kernel comparison harness.\n"
            "Run with --smoke to stage a race between mock kernels and see the report.\n"
            "In the repo: `from forge.kernel.harness import compare, BenchTask, "
            "ScriptedJudge` and pass your real adapters.\n"
        )