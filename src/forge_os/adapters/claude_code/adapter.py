"""ClaudeCodeAdapter — real kernel adapter over the claude CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_os.adapters.base import AgentHandle, BaseKernelAdapter, ToolList
from forge_os.adapters.claude_code.runner import RunResult, run_claude
from forge_os.adapters.claude_code.tool_map import DEFAULT_ABSTRACT_TOOLS, to_claude_tools
from forge_os.agents.models import AgentDefinition, OutputArtifact


class ClaudeCodeAdapter(BaseKernelAdapter):
    """Kernel adapter that drives Claude Code via subprocess + stream-json.

    Slice 1: subprocess invocation and stream-json parsing.
    Slice 2 (planned): hook capture + event-store write.
    Slice 3 (planned): replay from event store.
    """

    adapter_id = "claude-code"
    optional_capabilities = frozenset({"stream", "hook_events", "replay"})

    def __init__(
        self,
        project_root: Path | str,
        *,
        claude_bin: str = "claude",
        max_turns: int = 10,
        timeout: int = 120,
    ) -> None:
        self.project_root = Path(project_root)
        self.claude_bin = claude_bin
        self.max_turns = max_turns
        self.timeout = timeout

    def get_default_tools(self) -> ToolList:
        return list(DEFAULT_ABSTRACT_TOOLS)

    def spawn_agent(
        self,
        persona: AgentDefinition,
        context: str,
        tools: ToolList,
    ) -> AgentHandle:
        """Invoke claude CLI and return a completed AgentHandle.

        Raises ClaudeCodeSpawnError on non-zero exit or parse errors.
        """
        granted_abstract = self._intersect_tools(tools)
        claude_tools = to_claude_tools(granted_abstract)

        prompt = self._build_prompt(persona, context)

        result = run_claude(
            prompt,
            allowed_tools=claude_tools,
            cwd=self.project_root,
            max_turns=self.max_turns,
            timeout=self.timeout,
            claude_bin=self.claude_bin,
        )

        return self._build_handle(persona, granted_abstract, result)

    def _build_prompt(self, persona: AgentDefinition, context: str) -> str:
        parts = [f"Role: {persona.role}", f"\n{persona.prompt}"]
        if context:
            parts.append(f"\n\nContext:\n{context}")
        return "\n".join(parts)

    def _build_handle(
        self,
        persona: AgentDefinition,
        granted_tools: list[str],
        result: RunResult,
    ) -> AgentHandle:
        outputs = self._extract_outputs(result)
        return AgentHandle(
            provider=self.adapter_id,
            persona_id=persona.id,
            stage_id=persona.stage_ids[0] if persona.stage_ids else None,
            status="completed",
            outputs=outputs,
            metadata=self._build_metadata(persona, granted_tools, result),
        )

    def _extract_outputs(self, result: RunResult) -> list[OutputArtifact]:
        text = result.text_output
        if not text:
            return []
        return [OutputArtifact(path="", kind="text", description=text[:500])]

    def _build_metadata(
        self,
        persona: AgentDefinition,
        granted_tools: list[str],
        result: RunResult,
    ) -> dict[str, Any]:
        return {
            "adapter": self.adapter_id,
            "tools_granted": granted_tools,
            "tool_use_count": len(result.tool_uses),
            "event_count": len(result.events),
            "text_length": len(result.text_output),
            "returncode": result.returncode,
        }
