"""Tests for ACP backend: ACPClient, ACPRegistryAdapter, and ACPUseCases."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_os.kernel.acp_client import ACPClient, ACPClientError, SessionInfo
from forge_os.kernel.acp_registry_adapter import (
    ACPRegistryAdapter,
    ACPRegistryError,
    DistributionType,
)
from forge_os.use_cases.acp import ACPUseCases

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def registry_data() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "agents": [
            {
                "id": "test-agent",
                "name": "Test Coding Agent",
                "version": "1.0.0",
                "description": "A test agent",
                "distribution": {
                    "npx": {"package": "@test/agent", "args": ["--acp"]},
                    "uvx": {"package": "test-agent", "args": ["serve"]},
                },
                "repository": "https://github.com/test/agent",
                "authors": ["Test Author"],
                "license": "MIT",
            },
            {
                "id": "binary-agent",
                "name": "Binary Only Agent",
                "version": "2.0.0",
                "description": "A binary-only agent",
                "distribution": {
                    "binary": {
                        "linux-x86_64": {
                            "archive": "https://example.com/agent-linux.tar.gz",
                            "cmd": "agent",
                            "args": [],
                        },
                        "darwin-aarch64": {
                            "archive": "https://example.com/agent-darwin.tar.gz",
                            "cmd": "agent",
                            "args": [],
                        },
                    }
                },
                "license": "Apache-2.0",
            },
        ],
    }


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".forge" / "acp"


# ── ACPRegistryAdapter tests ─────────────────────────────────────────────────


class TestACPRegistryAdapter:
    def test_parse_registry(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        # Inject cache directly
        ACPRegistryAdapter._registry_cache = registry_data

        agents = adapter.list_agents()
        assert len(agents) == 2
        assert agents[0].id == "test-agent"
        assert agents[0].name == "Test Coding Agent"
        assert agents[0].distribution_npx is not None
        assert agents[0].distribution_npx.package == "@test/agent"
        assert agents[0].distribution_uvx is not None
        assert agents[0].license == "MIT"

    def test_get_agent_manifest_found(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        manifest = adapter.get_agent_manifest("test-agent")
        assert manifest is not None
        assert manifest.name == "Test Coding Agent"

    def test_get_agent_manifest_not_found(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        manifest = adapter.get_agent_manifest("nonexistent")
        assert manifest is None

    def test_npx_install_resolution(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        manifest = adapter.get_agent_manifest("test-agent")
        assert manifest is not None
        dist = adapter._resolve_distribution(manifest, DistributionType.NPX)
        assert dist == DistributionType.NPX

    def test_install_npx(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        result = adapter.install_agent("test-agent", distribution_type="npx")
        assert "npx -y @test/agent@latest" in result

    def test_install_uvx(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        result = adapter.install_agent("test-agent", distribution_type="uvx")
        assert "uvx test-agent@latest" in result

    def test_uninstall_agent(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        # Install first
        adapter.install_agent("test-agent", distribution_type="npx")
        assert len(adapter.get_installed_agents()) == 1

        # Then uninstall
        assert adapter.uninstall_agent("test-agent") is True
        assert len(adapter.get_installed_agents()) == 0

    def test_uninstall_nonexistent(self, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        assert adapter.uninstall_agent("nonexistent") is False

    def test_get_installed_agents_empty(self, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        assert adapter.get_installed_agents() == []

    def test_manifest_list_uses_class_cache(self, registry_data: dict, cache_dir: Path) -> None:
        """Direct registry cache injection is used by list_agents()."""
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        agents = adapter.list_agents()
        assert len(agents) == 2
        assert agents[0].id == "test-agent"

    def test_platform_key_detection(self) -> None:
        key = ACPRegistryAdapter._platform_key()
        assert "-" in key
        parts = key.split("-")
        assert len(parts) == 2
        assert parts[0] in ("darwin", "linux", "windows")
        assert parts[1] in ("x86_64", "aarch64")

    def test_parse_binary_only_agent(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        manifest = adapter.get_agent_manifest("binary-agent")
        assert manifest is not None
        assert manifest.distribution_npx is None
        assert manifest.distribution_uvx is None
        assert "linux-x86_64" in manifest.distribution_binary

    def test_auto_resolve_prefers_npx(self, registry_data: dict, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        ACPRegistryAdapter._registry_cache = registry_data

        manifest = adapter.get_agent_manifest("test-agent")
        assert manifest is not None
        dist = adapter._resolve_distribution(manifest, None)
        assert dist == DistributionType.NPX

    def test_registry_error_on_unknown_agent(self, cache_dir: Path) -> None:
        adapter = ACPRegistryAdapter(cache_dir)
        with pytest.raises(ACPRegistryError, match="not found in registry"):
            adapter.install_agent("unknown-agent")

    def test_registry_error_on_no_distribution(self, cache_dir: Path) -> None:
        """An agent manifest with no distribution methods raises."""
        ACPRegistryAdapter._registry_cache = {
            "agents": [
                {
                    "id": "no-dist",
                    "name": "No Distribution",
                    "version": "1.0.0",
                    "description": "Has no distribution",
                    "distribution": {},
                }
            ]
        }
        adapter = ACPRegistryAdapter(cache_dir)
        with pytest.raises(ACPRegistryError, match="no supported distribution"):
            adapter.install_agent("no-dist")


# ── ACPClient tests ──────────────────────────────────────────────────────────


class TestACPClient:
    def test_requires_process_to_send(self) -> None:
        client = ACPClient(["echo", "hello"])
        with pytest.raises(ACPClientError, match="not running"):
            client._send({"jsonrpc": "2.0", "method": "test", "id": 1})

    def test_requires_process_to_receive(self) -> None:
        client = ACPClient(["echo", "hello"])
        with pytest.raises(ACPClientError, match="not running"):
            client._receive()

    def test_build_request_increments_id(self) -> None:
        client = ACPClient(["echo"])
        r1 = client._build_request("test", {})
        r2 = client._build_request("test", {})
        assert r1["id"] == 1
        assert r2["id"] == 2
        assert r1["jsonrpc"] == "2.0"

    def test_is_running_false_when_not_started(self) -> None:
        client = ACPClient(["echo"])
        assert client.is_running is False

    def test_stop_noop_when_not_started(self) -> None:
        client = ACPClient(["echo"])
        client.stop()  # Should not raise


# ── ACPUseCases tests ────────────────────────────────────────────────────────


class TestACPUseCases:
    def test_discover_agents(self, registry_data: dict, tmp_path: Path) -> None:
        ACPRegistryAdapter._registry_cache = registry_data
        use_cases = ACPUseCases(tmp_path)
        agents = use_cases.discover_agents()
        assert len(agents) == 2
        assert agents[0]["id"] == "test-agent"
        assert "npx" in agents[0]["distribution_types"]

    def test_install_agent(self, registry_data: dict, tmp_path: Path) -> None:
        ACPRegistryAdapter._registry_cache = registry_data
        use_cases = ACPUseCases(tmp_path)
        path = use_cases.install_agent("test-agent", distribution_method="npx")
        assert path is not None

    def test_list_installed_agents(self, registry_data: dict, tmp_path: Path) -> None:
        ACPRegistryAdapter._registry_cache = registry_data
        use_cases = ACPUseCases(tmp_path)
        assert len(use_cases.list_installed_agents()) == 0
        use_cases.install_agent("test-agent", distribution_method="npx")
        installed = use_cases.list_installed_agents()
        assert len(installed) == 1
        assert installed[0]["id"] == "test-agent"

    def test_uninstall_agent(self, registry_data: dict, tmp_path: Path) -> None:
        ACPRegistryAdapter._registry_cache = registry_data
        use_cases = ACPUseCases(tmp_path)
        use_cases.install_agent("test-agent", distribution_method="npx")
        assert use_cases.uninstall_agent("test-agent") is True
        assert len(use_cases.list_installed_agents()) == 0


# ── ACPUseCases session tests (P10 WS-C) ─────────────────────────────────────


class FakeSessionClient:
    """ACPClient stand-in serving a fixed session list, tracking lifecycle calls."""

    def __init__(self, sessions: list[SessionInfo]) -> None:
        self.sessions = sessions
        self.started = 0
        self.stopped = 0
        self.closed: list[str] = []

    def start(self) -> dict:
        self.started += 1
        return {}

    def stop(self) -> None:
        self.stopped += 1

    def session_list(self) -> list[SessionInfo]:
        return list(self.sessions)

    def session_close(self, session_id: str) -> None:
        self.closed.append(session_id)


class TestACPUseCasesSessions:
    @staticmethod
    def install_agents(project_root: Path, *agent_ids: str) -> None:
        import json

        acp_dir = project_root / ".forge" / "acp"
        acp_dir.mkdir(parents=True, exist_ok=True)
        (acp_dir / "installed.json").write_text(
            json.dumps(
                {
                    agent_id: {
                        "id": agent_id,
                        "name": agent_id,
                        "version": "1.0.0",
                        "distribution_type": "npx",
                        "install_path": f"npx -y {agent_id}@latest",
                    }
                    for agent_id in agent_ids
                }
            ),
            encoding="utf-8",
        )

    def test_list_sessions_empty_when_no_agents_installed(self, tmp_path: Path) -> None:
        def factory(command: list[str]):  # pragma: no cover - must not be called
            raise AssertionError("no client should be built without installed agents")

        use_cases = ACPUseCases(tmp_path, client_factory=factory)
        assert use_cases.list_sessions() == []

    def test_list_sessions_returns_sessions_from_installed_agent(self, tmp_path: Path) -> None:
        self.install_agents(tmp_path, "agent-a")
        client = FakeSessionClient([SessionInfo(id="s1", title="First")])
        use_cases = ACPUseCases(tmp_path, client_factory=lambda command: client)

        sessions = use_cases.list_sessions()

        assert sessions == [{"id": "s1", "agent_id": "agent-a", "title": "First", "metadata": {}}]
        assert client.started == 1
        assert client.stopped == 1

    def test_list_sessions_filters_by_agent_id(self, tmp_path: Path) -> None:
        self.install_agents(tmp_path, "agent-a", "agent-b")
        clients_built: list[FakeSessionClient] = []

        def factory(command: list[str]) -> FakeSessionClient:
            client = FakeSessionClient([SessionInfo(id=f"s{len(clients_built)}")])
            clients_built.append(client)
            return client

        use_cases = ACPUseCases(tmp_path, client_factory=factory)

        sessions = use_cases.list_sessions(agent_id="agent-b")

        assert len(sessions) == 1
        assert sessions[0]["agent_id"] == "agent-b"
        assert len(clients_built) == 1

    def test_close_session_closes_on_owning_agent(self, tmp_path: Path) -> None:
        self.install_agents(tmp_path, "agent-a")
        client = FakeSessionClient([SessionInfo(id="s1")])
        use_cases = ACPUseCases(tmp_path, client_factory=lambda command: client)

        use_cases.close_session("s1")

        assert client.closed == ["s1"]
        assert client.stopped == 1

    def test_close_session_raises_when_session_unknown(self, tmp_path: Path) -> None:
        self.install_agents(tmp_path, "agent-a")
        client = FakeSessionClient([SessionInfo(id="other")])
        use_cases = ACPUseCases(tmp_path, client_factory=lambda command: client)

        with pytest.raises(ACPClientError, match="not found"):
            use_cases.close_session("missing")
        assert client.closed == []

    def test_close_session_raises_when_no_agents_installed(self, tmp_path: Path) -> None:
        use_cases = ACPUseCases(tmp_path, client_factory=lambda command: None)

        with pytest.raises(ACPClientError, match="No ACP agents installed"):
            use_cases.close_session("s1")
