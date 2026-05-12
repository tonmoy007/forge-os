"""ACPRegistryAdapter — fetch, parse, cache, and install ACP registry agents.

The ACP Registry is a curated catalog at
https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
that allows discovery and installation of ACP-compatible coding agents.

Distribution methods:
- binary — platform-specific archives (darwin/linux/windows)
- npx — Node.js packages via `npx -y <package>@latest`
- uvx — Python packages via `uvx <package>@latest`
"""

from __future__ import annotations

import json
import platform
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class DistributionType(StrEnum):
    BINARY = "binary"
    NPX = "npx"
    UVX = "uvx"


@dataclass
class BinaryDistribution:
    archive: str
    cmd: str
    args: list[str] = field(default_factory=list)


@dataclass
class PackageDistribution:
    package: str
    args: list[str] = field(default_factory=list)


@dataclass
class AgentManifest:
    """Parsed manifest for an ACP agent from the registry."""

    id: str
    name: str
    version: str
    description: str | None = None
    distribution_binary: dict[str, BinaryDistribution] = field(default_factory=dict)
    distribution_npx: PackageDistribution | None = None
    distribution_uvx: PackageDistribution | None = None
    repository: str | None = None
    authors: list[str] = field(default_factory=list)
    license: str | None = None
    icon: str | None = None


class ACPRegistryError(RuntimeError):
    """Raised when ACP registry operations fail."""


class ACPRegistryAdapter:
    """Discover, fetch, and install agents from the ACP Registry.

    Caches registry JSON locally under <project_root>/.forge/acp/.
    Installed agents are tracked in <project_root>/.forge/acp/installed.json.
    """

    REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
    _registry_cache: dict[str, Any] | None = None  # class-level for session reuse

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir.resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Registry Fetch ─────────────────────────────────────────────────────

    def fetch_registry(self, force: bool = False) -> dict[str, Any]:
        """Fetch the full ACP registry JSON.

        Results are cached in memory for the session lifetime.
        Set force=True to re-fetch from the CDN.
        """
        if not force and ACPRegistryAdapter._registry_cache is not None:
            return ACPRegistryAdapter._registry_cache

        try:
            req = urllib.request.Request(
                self.REGISTRY_URL,
                headers={"User-Agent": "ForgeOS/0.5.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode())
        except Exception as exc:
            raise ACPRegistryError(f"Failed to fetch ACP registry: {exc}") from exc

        ACPRegistryAdapter._registry_cache = data
        # Write local cache
        cache_file = self.cache_dir / "registry.json"
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    # ── Agent Discovery ─────────────────────────────────────────────────────

    def list_agents(self) -> list[AgentManifest]:
        """List all agents available in the ACP Registry."""
        registry = self.fetch_registry()
        raw_agents: list[dict[str, Any]] = registry.get("agents", [])
        return [self._parse_manifest(a) for a in raw_agents]

    def get_agent_manifest(self, agent_id: str) -> AgentManifest | None:
        """Retrieve a specific agent's manifest from the registry."""
        for manifest in self.list_agents():
            if manifest.id == agent_id:
                return manifest
        return None

    # ── Installation ────────────────────────────────────────────────────────

    def install_agent(
        self,
        agent_id: str,
        distribution_type: str | None = None,
    ) -> str:
        """Install an ACP agent and return its runnable command path.

        Args:
            agent_id: Unique identifier from the registry.
            distribution_type: One of 'binary', 'npx', 'uvx', or None for auto.

        Returns:
            A command string or path suitable for spawning via ACPClient.

        Raises:
            ACPRegistryError: If the agent is not found or installation fails.
        """
        manifest = self.get_agent_manifest(agent_id)
        if manifest is None:
            raise ACPRegistryError(f"Agent '{agent_id}' not found in registry")

        dist_type = self._resolve_distribution(manifest, distribution_type)
        install_path = self._do_install(manifest, dist_type)
        self._record_installation(manifest, dist_type, install_path)
        return install_path

    def uninstall_agent(self, agent_id: str) -> bool:
        """Remove an installed ACP agent's local metadata.

        Returns True if the agent was previously installed.
        """
        installed = self._load_installed()
        if agent_id not in installed:
            return False
        del installed[agent_id]
        self._save_installed(installed)
        return True

    def get_installed_agents(self) -> list[dict[str, Any]]:
        """Return metadata for all locally installed ACP agents."""
        return list(self._load_installed().values())

    # ── Availability ────────────────────────────────────────────────────────

    def is_registry_accessible(self) -> bool:
        """Check if the ACP Registry CDN is reachable."""
        try:
            req = urllib.request.Request(
                self.REGISTRY_URL,
                headers={"User-Agent": "ForgeOS/0.5.0"},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:  # noqa: BLE001
            return False

    def check_agent_availability(self, agent_id: str) -> bool:
        """Check if an agent is registered in the ACP Registry."""
        return self.get_agent_manifest(agent_id) is not None

    # ── Private Helpers ────────────────────────────────────────────────────

    def _parse_manifest(self, raw: dict[str, Any]) -> AgentManifest:
        dist = raw.get("distribution", {})

        binary_raw: dict[str, Any] = dist.get("binary", {})
        distribution_binary: dict[str, BinaryDistribution] = {}
        for os_arch, info in binary_raw.items():
            if isinstance(info, dict):
                distribution_binary[os_arch] = BinaryDistribution(
                    archive=info.get("archive", ""),
                    cmd=info.get("cmd", ""),
                    args=info.get("args", []),
                )

        npx_raw = dist.get("npx")
        distribution_npx: PackageDistribution | None = None
        if isinstance(npx_raw, dict):
            distribution_npx = PackageDistribution(
                package=npx_raw.get("package", ""),
                args=npx_raw.get("args", []),
            )

        uvx_raw = dist.get("uvx")
        distribution_uvx: PackageDistribution | None = None
        if isinstance(uvx_raw, dict):
            distribution_uvx = PackageDistribution(
                package=uvx_raw.get("package", ""),
                args=uvx_raw.get("args", []),
            )

        return AgentManifest(
            id=raw.get("id", ""),
            name=raw.get("name", ""),
            version=raw.get("version", ""),
            description=raw.get("description"),
            distribution_binary=distribution_binary,
            distribution_npx=distribution_npx,
            distribution_uvx=distribution_uvx,
            repository=raw.get("repository"),
            authors=raw.get("authors", []),
            license=raw.get("license"),
            icon=raw.get("icon"),
        )

    def _resolve_distribution(
        self,
        manifest: AgentManifest,
        preferred: str | None,
    ) -> str:
        valid = {DistributionType.BINARY, DistributionType.NPX, DistributionType.UVX}
        if preferred and preferred in valid:
            return preferred

        # Auto-resolve: prefer npx > uvx > binary
        if manifest.distribution_npx:
            return DistributionType.NPX
        if manifest.distribution_uvx:
            return DistributionType.UVX
        if manifest.distribution_binary:
            return DistributionType.BINARY
        raise ACPRegistryError(f"Agent '{manifest.id}' has no supported distribution method")

    def _do_install(self, manifest: AgentManifest, dist_type: str) -> str:
        if dist_type == DistributionType.NPX:
            return self._install_npx(manifest)
        if dist_type == DistributionType.UVX:
            return self._install_uvx(manifest)
        if dist_type == DistributionType.BINARY:
            return self._install_binary(manifest)
        raise ACPRegistryError(f"Unknown distribution type: {dist_type}")

    def _install_npx(self, manifest: AgentManifest) -> str:
        if manifest.distribution_npx is None:
            raise ACPRegistryError(f"Agent '{manifest.id}' has no npx distribution")
        pkg = manifest.distribution_npx.package
        # npx is run directly — no download needed; cache the command string
        return f"npx -y {pkg}@latest"

    def _install_uvx(self, manifest: AgentManifest) -> str:
        if manifest.distribution_uvx is None:
            raise ACPRegistryError(f"Agent '{manifest.id}' has no uvx distribution")
        pkg = manifest.distribution_uvx.package
        return f"uvx {pkg}@latest"

    def _install_binary(self, manifest: AgentManifest) -> str:
        dist = self._get_platform_distribution(manifest)
        if dist is None:
            raise ACPRegistryError(
                f"No binary distribution for current platform in agent '{manifest.id}'"
            )

        agent_dir = self.cache_dir / "bin" / manifest.id
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Download archive
        archive_path = agent_dir / self._archive_name(dist.archive)
        if not archive_path.exists():
            try:
                req = urllib.request.Request(
                    dist.archive,
                    headers={"User-Agent": "ForgeOS/0.5.0"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    archive_path.write_bytes(resp.read())
            except Exception as exc:
                raise ACPRegistryError(
                    f"Failed to download {manifest.id}: {exc}"
                ) from exc

        # Extract archive
        self._extract_archive(archive_path, agent_dir)

        # Make binary executable
        binary_path = agent_dir / dist.cmd
        if binary_path.exists():
            binary_path.chmod(binary_path.stat().st_mode | 0o111)

        return str(binary_path.resolve())

    # ── Persistence ─────────────────────────────────────────────────────────

    def _load_installed(self) -> dict[str, Any]:
        path = self.cache_dir / "installed.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _save_installed(self, data: dict[str, Any]) -> None:
        path = self.cache_dir / "installed.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _record_installation(
        self,
        manifest: AgentManifest,
        dist_type: str,
        install_path: str,
    ) -> None:
        installed = self._load_installed()
        installed[manifest.id] = {
            "id": manifest.id,
            "name": manifest.name,
            "version": manifest.version,
            "distribution_type": dist_type,
            "install_path": install_path,
            "description": manifest.description,
        }
        self._save_installed(installed)

    # ── Platform helpers ───────────────────────────────────────────────────

    def _get_platform_distribution(
        self,
        manifest: AgentManifest,
    ) -> BinaryDistribution | None:
        key = self._platform_key()
        return manifest.distribution_binary.get(key)

    @staticmethod
    def _platform_key() -> str:
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("aarch64", "arm64"):
            arch = "aarch64"
        else:
            arch = machine

        system = platform.system().lower()
        if system == "darwin":
            return f"darwin-{arch}"
        if system == "linux":
            return f"linux-{arch}"
        if system == "windows":
            return f"windows-{arch}"
        return f"{system}-{arch}"

    @staticmethod
    def _archive_name(url: str) -> str:
        return url.rsplit("/", 1)[-1] if "/" in url else url

    @staticmethod
    def _extract_archive(archive_path: Path, target_dir: Path) -> None:
        """Extract a tar.gz or zip archive."""
        suffix = "".join(archive_path.suffixes)
        if suffix.endswith(".tar.gz") or suffix.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=target_dir)
        elif suffix.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(path=target_dir)
        else:
            # Assume it's a single binary, no extraction needed
            pass
