"""Tests for Phase 08.5 async adapter protocol and implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.adapters.async_base import (
    AsyncAgentHandle,
    AsyncBaseKernelAdapter,
    AsyncEventResponse,
    AsyncKernelAdapter,
)
from forge_os.adapters.async_dummy import AsyncDummyAdapter
from forge_os.agents.models import AgentDefinition
from forge_os.schemas.state import PipelineState

# ── AsyncDummyAdapter tests ─────────────────────────────────────────────────


class TestAsyncDummyAdapter:
    @pytest.fixture
    def project_root(self, tmp_path: Path) -> Path:
        root = tmp_path / "async-test-project"
        root.mkdir(parents=True)
        return root

    @pytest.fixture
    def persona(self) -> AgentDefinition:
        return AgentDefinition(
            id="async-test-persona",
            name="Async Test Persona",
            category="stage",
            role="test role",
            prompt="test prompt",
            stage_ids=["srs"],
            default_tools=["read_file"],
        )

    @pytest.fixture
    def state(self) -> PipelineState:
        return PipelineState(
            project_id="async-test",
            profile="minimal",
            current_stage_id="srs",
            stages=[],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

    async def test_async_dummy_adapter_protocol_compliance(self) -> None:
        """AsyncDummyAdapter satisfies the AsyncKernelAdapter protocol."""
        adapter = AsyncDummyAdapter()
        assert isinstance(adapter, AsyncKernelAdapter)

    async def test_async_dummy_spawn_agent_returns_handle(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = AsyncDummyAdapter(project_root, create_outputs=True)
        handle = await adapter.spawn_agent(persona, "test context", ["read_file"])
        assert isinstance(handle, AsyncAgentHandle)
        assert handle.status == "completed"
        assert handle.provider == "async-dummy"
        assert handle.persona_id == "async-test-persona"

    async def test_async_dummy_spawn_without_outputs(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = AsyncDummyAdapter(project_root, create_outputs=False)
        handle = await adapter.spawn_agent(persona, "test context", ["read_file"])
        assert handle.status == "completed"
        assert len(handle.outputs) == 0

    async def test_async_dummy_no_project_root(
        self, persona: AgentDefinition
    ) -> None:
        adapter = AsyncDummyAdapter(create_outputs=True)
        handle = await adapter.spawn_agent(persona, "test", ["read_file"])
        assert handle.status == "completed"
        assert len(handle.outputs) == 0

    async def test_async_dummy_spawn_creates_output_file(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        adapter = AsyncDummyAdapter(project_root, create_outputs=True)
        handle = await adapter.spawn_agent(persona, "context", ["read_file"])
        assert len(handle.outputs) == 1
        output_path = project_root / handle.outputs[0].path
        assert output_path.exists()
        content = output_path.read_text()
        assert "Async Test Persona" in content

    async def test_async_dummy_get_default_tools(self) -> None:
        adapter = AsyncDummyAdapter()
        tools = await adapter.get_default_tools()
        assert "read_file" in tools
        assert "write_file" in tools
        assert "list_files" in tools

    async def test_async_dummy_on_event(
        self, project_root: Path, state: PipelineState
    ) -> None:
        from forge_os.events.model import new_event

        adapter = AsyncDummyAdapter(project_root)
        event = new_event(
            "StageStarted",
            stage_id="srs",
            actor_type="user",
            actor_id="test",
            payload={},
        )
        response = await adapter.on_event(event, state)
        assert isinstance(response, AsyncEventResponse)
        assert response.handled is True

    async def test_async_dummy_supports(self) -> None:
        adapter = AsyncDummyAdapter()
        assert await adapter.supports("stop_agent") is True
        assert await adapter.supports("nonexistent") is False

    async def test_async_dummy_acp_not_available(self) -> None:
        adapter = AsyncDummyAdapter()
        assert await adapter.is_acp_available() is False
        agents = await adapter.list_acp_agents()
        assert agents == []

    async def test_async_dummy_output_matches_sync_version(
        self, project_root: Path, persona: AgentDefinition
    ) -> None:
        """Async DummyAdapter produces the same output structure as sync DummyAdapter."""
        from forge_os.adapters.dummy import DummyAdapter

        async_adapter = AsyncDummyAdapter(project_root, create_outputs=True)
        sync_adapter = DummyAdapter(project_root, create_outputs=True)

        async_handle = await async_adapter.spawn_agent(persona, "context", ["read_file"])
        sync_handle = sync_adapter.spawn_agent(persona, "context", ["read_file"])

        assert async_handle.status == sync_handle.status
        assert async_handle.persona_id == sync_handle.persona_id
        assert len(async_handle.outputs) == len(sync_handle.outputs)

        if async_handle.outputs and sync_handle.outputs:
            assert async_handle.outputs[0].path == sync_handle.outputs[0].path

    async def test_run_stage_agent_async(
        self, project_root: Path, state: PipelineState
    ) -> None:
        """Async agent executor produces a valid AgentRunRecord."""
        from forge_os.agents.executor import run_stage_agent_async
        from forge_os.project.scaffold import initialize_project

        initialize_project(project_root, project_name="async-test", profile="minimal")

        record = await run_stage_agent_async(project_root, state, "srs")
        assert record is not None
        assert record.stage_id == "srs"
        assert record.status == "completed"
        assert record.adapter == "async-dummy"
        assert record.metadata.get("async") is True

    async def test_run_stage_agent_async_no_project(
        self, tmp_path: Path, state: PipelineState
    ) -> None:
        """Async executor raises on uninitialized project."""
        from forge_os.agents.executor import AgentExecutionError, run_stage_agent_async

        with pytest.raises(AgentExecutionError):
            await run_stage_agent_async(tmp_path, state, "srs")


# ── AsyncBaseKernelAdapter tests ────────────────────────────────────────────


class TestAsyncBaseKernelAdapter:
    async def test_default_supports(self) -> None:
        adapter = AsyncBaseKernelAdapter()
        assert await adapter.supports("anything") is False

    async def test_default_acp_not_available(self) -> None:
        adapter = AsyncBaseKernelAdapter()
        assert await adapter.is_acp_available() is False

    async def test_default_get_tools(self) -> None:
        adapter = AsyncBaseKernelAdapter()
        tools = await adapter.get_default_tools()
        assert tools == []

    async def test_default_on_event(self) -> None:
        from forge_os.events.model import new_event
        from forge_os.schemas.state import PipelineState

        adapter = AsyncBaseKernelAdapter()
        state = PipelineState(
            project_id="test",
            profile="minimal",
            current_stage_id=None,
            stages=[],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        event = new_event(
            "StageStarted",
            stage_id="srs",
            actor_type="user",
            actor_id="test",
            payload={},
        )
        response = await adapter.on_event(event, state)
        assert response.handled is True
        assert "observed" in (response.message or "")

    async def test_intersect_tools(self) -> None:
        adapter = AsyncBaseKernelAdapter()
        result = await adapter._intersect_tools(["read_file", "write_file"])
        assert result == []  # no defaults set

    async def test_default_acp_methods_raise(self) -> None:
        from forge_os.adapters.base import UnsupportedAdapterCapability

        adapter = AsyncBaseKernelAdapter()
        with pytest.raises(UnsupportedAdapterCapability):
            await adapter.get_acp_registry_adapter()
        with pytest.raises(UnsupportedAdapterCapability):
            await adapter.spawn_acp_agent("test-agent")


# ── Async HTTP client tests ─────────────────────────────────────────────────


class TestAsyncHTTPClient:
    async def test_missing_url_raises(self) -> None:
        from forge_os.kernel.http import AsyncHTTPClient, AsyncHTTPError

        client = AsyncHTTPClient()
        with pytest.raises(AsyncHTTPError):
            await client.get("http://nonexistent.example.invalid")

    async def test_client_defaults(self) -> None:
        from forge_os.kernel.http import AsyncHTTPClient

        client = AsyncHTTPClient(timeout=30, max_retries=0)
        assert client.timeout == 30
        assert client.max_retries == 0
        assert "ForgeOS" in client.headers.get("User-Agent", "")
