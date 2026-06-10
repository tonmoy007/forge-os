"""ACP use cases — business logic bridging CLI to ACP backend."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from forge_os.kernel.acp_client import (
    ACPClient,
    ACPClientError,
    agent_command_from_install,
)
from forge_os.kernel.acp_registry_adapter import ACPRegistryAdapter


class ACPUseCases:
    """Business logic layer for ACP agent discovery, installation, and session management."""

    def __init__(
        self,
        project_root: Path,
        *,
        client_factory: Callable[[list[str]], Any] | None = None,
    ) -> None:
        cache_dir = project_root / ".forge" / "acp"
        self.registry = ACPRegistryAdapter(cache_dir)
        self._client_factory = client_factory or (lambda command: ACPClient(command))

    def discover_agents(self) -> list[dict[str, Any]]:
        """Fetch available ACP agents from the official registry.

        Returns a list of dicts matching the CLI display schema.
        Raises if registry is unreachable.
        """
        manifests = self.registry.list_agents()
        return [
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "description": m.description or "",
                "license": m.license or "",
                "distribution_types": self._distribution_types(m),
                "repository": m.repository or "",
            }
            for m in manifests
        ]

    def list_installed_agents(self) -> list[dict[str, Any]]:
        """Return metadata for locally installed ACP agents."""
        return self.registry.get_installed_agents()

    def install_agent(
        self,
        agent_id: str,
        distribution_method: str | None = None,
    ) -> str:
        """Install an ACP agent and return its runnable command path.

        Raises ACPRegistryError if the agent is not found or install fails.
        """
        return self.registry.install_agent(agent_id, distribution_method)

    def uninstall_agent(self, agent_id: str) -> bool:
        """Remove an installed agent's local metadata."""
        return self.registry.uninstall_agent(agent_id)

    def list_sessions(self, agent_id: str | None = None) -> list[dict[str, Any]]:
        """List active ACP sessions across installed agents via `session/list`.

        Returns [] when no agents are installed. Connection failures
        propagate as ACPClientError for the CLI to render.
        """
        installed = self.registry.get_installed_agents()
        if agent_id:
            installed = [a for a in installed if a.get("id") == agent_id]
        sessions: list[dict[str, Any]] = []
        for agent in installed:
            client = self._client_factory(agent_command_from_install(agent))
            client.start()
            try:
                for info in client.session_list():
                    sessions.append(
                        {
                            "id": info.id,
                            "agent_id": agent.get("id", ""),
                            "title": info.title or "",
                            "metadata": info.metadata,
                        }
                    )
            finally:
                client.stop()
        return sessions

    def close_session(self, session_id: str) -> None:
        """Close an ACP session by ID on whichever installed agent owns it.

        Raises ACPClientError when no agents are installed or no installed
        agent reports the session.
        """
        installed = self.registry.get_installed_agents()
        if not installed:
            raise ACPClientError("No ACP agents installed; there is no session to close.")
        for agent in installed:
            client = self._client_factory(agent_command_from_install(agent))
            client.start()
            try:
                if any(info.id == session_id for info in client.session_list()):
                    client.session_close(session_id)
                    return
            finally:
                client.stop()
        raise ACPClientError(f"Session '{session_id}' not found on any installed agent.")

    @staticmethod
    def _distribution_types(manifest: Any) -> list[str]:
        types: list[str] = []
        if manifest.distribution_binary:
            types.append("binary")
        if manifest.distribution_npx:
            types.append("npx")
        if manifest.distribution_uvx:
            types.append("uvx")
        return types

