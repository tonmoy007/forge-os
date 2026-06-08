"""
forge.kernel.opencode_mcp_proxy
===============================

Standalone MCP stdio server that bridges OpenCode → Forge for custom tools.

This script is NOT imported. It runs as a grandchild process:

    Forge Python  →  spawns  →  `opencode serve` (Bun)  →  spawns  →  THIS script

OpenCode discovers it via the per-session MCP config that the adapter writes:

    {"mcp": {"forge_proxy": {
        "type": "local",
        "command": ["python", "-m", "forge.kernel.opencode_mcp_proxy"],
        "enabled": True,
        "environment": {
            "FORGE_BACKCHANNEL_URL": "http://127.0.0.1:<port>",
            "FORGE_SESSION_ID": "<session_id>",
        },
    }}}

Every tool call follows the same path:

    Model decides to call forge_propose_event(...)
        │
        ▼
    OpenCode → MCP stdio → THIS script's @mcp.tool() function
        │
        ▼
    POST {backchannel_url}/propose
        { session_id, abstract_tool, inputs, call_id }
        │
        ▼
    Forge adapter's back-channel handler:
        - constructs ToolUseProposal
        - puts on session's events_q
        - spawn_agent yields it to caller
        - caller runs Validator + Executor
        - caller asend()s ToolResult
        - handler resolves Future, returns JSON
        │
        ▼
    THIS script returns the result string over MCP stdio
        │
        ▼
    OpenCode hands the result to the model

The proxy is deliberately dumb: it doesn't validate, doesn't execute, doesn't
decide. All policy lives in Forge. This is just a wire converter from MCP
stdio to HTTP loopback.

Dependencies
------------
    pip install "mcp>=1.0" "httpx>=0.27"

Run
---
    # Normally invoked by OpenCode as a subprocess. For manual testing:
    FORGE_BACKCHANNEL_URL=http://127.0.0.1:54321 \\
    FORGE_SESSION_ID=ses_abc \\
    python -m forge.kernel.opencode_mcp_proxy
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ----------------------------------------------------------------------------
# Boot-time configuration from env (passed by the adapter via OpenCode's MCP
# environment block). Failing fast here surfaces config bugs immediately
# instead of producing mysterious tool-call errors mid-session.
# ----------------------------------------------------------------------------

BACKCHANNEL  = os.environ.get("FORGE_BACKCHANNEL_URL")
AGGREGATE_ID = os.environ.get("FORGE_AGGREGATE_ID")
TIMEOUT_S    = float(os.environ.get("FORGE_PROXY_TIMEOUT_S", "120"))

if not BACKCHANNEL or not AGGREGATE_ID:
    print(
        "FATAL: opencode_mcp_proxy requires FORGE_BACKCHANNEL_URL and "
        "FORGE_AGGREGATE_ID env vars.",
        file=sys.stderr,
    )
    sys.exit(2)

# Reuse one client across calls — MCP stdio is single-threaded, so a single
# AsyncClient is safe and avoids per-call TCP setup.
_client = httpx.AsyncClient(timeout=TIMEOUT_S, base_url=BACKCHANNEL)

mcp = FastMCP("forge_proxy")


async def _call_back(abstract_tool: str, inputs: dict[str, Any]) -> str:
    """Forward an MCP tool invocation to Forge's back-channel.

    Returns the string content of the ToolResult. Errors are surfaced as
    string error messages — the model will see them and decide whether to
    retry. We deliberately do NOT raise inside MCP tool handlers: FastMCP
    converts exceptions into MCP-level errors, which OpenCode treats as
    transport failures rather than tool failures, which obscures Forge's
    denied-by-validator semantics.
    """
    call_id = f"mcp-{uuid.uuid4().hex[:12]}"
    body = {
        "aggregate_id": AGGREGATE_ID,
        "call_id":      call_id,
        "abstract_tool": abstract_tool,
        "inputs":       inputs,
    }
    try:
        r = await _client.post("/propose", json=body)
    except httpx.TimeoutException:
        return f"ERROR: Forge validator timed out after {TIMEOUT_S}s for {abstract_tool}"
    except httpx.HTTPError as e:
        return f"ERROR: back-channel transport failure: {e!r}"

    if r.status_code == 404:
        return f"ERROR: Forge has no record of aggregate {AGGREGATE_ID}"
    if r.status_code == 504:
        return f"ERROR: Forge validator timed out for {abstract_tool}"
    if r.status_code >= 400:
        return f"ERROR: back-channel returned {r.status_code}: {r.text}"

    payload = r.json()
    if "error" in payload:
        return f"ERROR: {payload['error']}"
    return payload.get("content", "")


# ----------------------------------------------------------------------------
# Forge custom tools — MUST stay in sync with FORGE_CUSTOM_TOOLS in
# opencode_adapter.py. In production both files import a shared registry
# from forge/kernel/tools.py.
# ----------------------------------------------------------------------------

@mcp.tool()
async def forge_propose_event(
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    """Propose a domain event for the Forge event store.

    The Validator checks the event against the aggregate's invariants and
    the Executor appends it to the event store if accepted. Returns a JSON
    string describing the outcome (accepted/rejected, sequence number, etc.).
    """
    return await _call_back("ProposeEvent", {
        "aggregate_id": aggregate_id,
        "event_type":   event_type,
        "payload":      payload,
    })


@mcp.tool()
async def forge_read_lkg(query: str) -> str:
    """Query Forge's Lessons Knowledge Graph for prior learnings.

    Read-only. Returns a JSON string with matched lessons and citations.
    """
    return await _call_back("ReadLKG", {"query": query})


# Add additional Forge tools here. Each MUST also be registered in
# opencode_adapter.FORGE_CUSTOM_TOOLS for the adapter's permission map
# and abstract-name mapping to work.


if __name__ == "__main__":
    # FastMCP.run() takes over stdin/stdout for the MCP protocol. Anything
    # printed to stdout after this would corrupt the MCP stream — use
    # stderr for diagnostics (OpenCode pipes proxy stderr to its log).
    mcp.run(transport="stdio")