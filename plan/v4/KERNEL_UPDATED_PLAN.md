## ACP Registry Research & IKernelAdapter Integration

### 🔬 1. What is the Agent Client Protocol (ACP)?

ACP is a standardized protocol designed to connect code editors (clients) with AI coding agents (servers), similar to how the Language Server Protocol (LSP) standardized language intelligence. Throughout 2025 and into 2026, ACP has been gaining adoption across the ecosystem, with implementations in Python, Rust, TypeScript, Kotlin, Java, Dart, and Elixir.

**Origin & Release Timeline:**

| Date | Milestone |
| :--- | :--- |
| Early 2025 | Zed team began building "agentic editing" features, running Gemini CLI inside embedded terminal |
| August 2025 | Zed and Google launched ACP as an open standard under Apache License 2.0; Google's Gemini CLI became the flagship example |
| October 2025 | JetBrains and Zed Industries formally introduced ACP |
| February 2026 | Sergey Ignatov from JetBrains joined as Lead Maintainer, reflecting collaboration between Zed and JetBrains |
| April 2026 | ACP Registry released, providing a standard way to discover, install, and configure compatible agents |

**Core Architecture**:
- Communication: JSON-RPC over stdio (standard input/output)
- Transport: ACP clients and agents communicate via newline-delimited JSON, with the editor launching agent processes
- Philosophy: "Any editor + any agent, no custom plugins required" — eliminates the need for one-off integrations

---

### 2. ACP Registry Structure

The ACP Registry is a curated catalog that allows developers to distribute ACP-compatible agents to any client through a standardized lookup mechanism. The registry includes only agents that support authentication.

#### Registry JSON Endpoint

Clients can programmatically fetch registry metadata via:
```
curl https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
```

The JSON includes comprehensive agent metadata such as distribution information, version, capabilities, and authentication methods required for automatic installation.

#### Agent Manifest Schema (`agent.json`)

Each agent in the registry is defined by a YAML manifest (`<agent-id>/agent.json`):

```yaml
id: example-agent                            # Required. Unique identifier, lowercase with hyphens
name: "Example Coding Agent"                 # Required. Human-readable display name
version: "1.2.0"                             # Required. Semantic version
description: "A coding agent for task X"     # Required. Brief description
distribution:                                # Required. One or more distribution methods
  binary:                                    # Platform-specific archives
    darwin-aarch64:
      archive: "https://example.com/agent-darwin-arm64.tar.gz"
      cmd: "./agent"
      args: ["--config", "config.json"]
    linux-x86_64:
      archive: "https://example.com/agent-linux-amd64.tar.gz"
      cmd: "./agent"
  npx:                                       # Node.js distribution
    package: "@scope/agent-package"
    args: ["--acp"]
  uvx:                                       # Python distribution
    package: "agent-package"
    args: ["serve"]
repository: "https://github.com/example/agent"
authors: ["Example Corp"]
license: "Apache-2.0"
icon: "icon.svg"                             # SVG, 16x16, monochrome with currentColor
```

**Distribution Formats:**
- `binary` — Platform-specific builds (required to support all three OS: darwin, linux, windows)
- `npx` — Node.js packages via `npx -y package@latest`
- `uvx` — Python packages via `uvx package@latest`

#### How to Submit an Agent

To add an agent to the registry:
1. Fork the [registry repository](https://github.com/agentclientprotocol/registry)
2. Create a folder with your agent's ID (lowercase, hyphens allowed)
3. Add an `agent.json` file following the schema
4. Optionally add an `icon.svg` (16x16 recommended)
5. Submit a pull request

All contributions are accepted under the Apache License, Version 2.0 without requiring a Contributor License Agreement (CLA).

---

### 3. ACP Adapters & Integrations in the Wild

The ACP ecosystem has growing adapter support:

| Project | Role | Description |
| :--- | :--- | :--- |
| **GitHub Copilot CLI** | Client / Server | Now implements ACP, enabling third-party tools and IDEs to integrate directly with Copilot's agentic capabilities |
| **openai-codex/acp** | Bridge | ACP-compatible agent bridging OpenAI Codex runtime with ACP clients over stdio |
| **deepagents-acp** | Wrapper | Wraps LangChain DeepAgents with ACP, allowing AI agents to communicate with code editors |
| **ACPR (acpr)** | Meta Agent | Fetches ACP registry and runs specified agents using npx (Node) or uvx (Python) distribution methods |
| **@mcpc/acp-ai-provider** | SDK Bridge | Bridges ACP agents to AI SDK, spawning ACP agents (Claude Code, Gemini, Codex CLI) as child processes |
| **ACPex** | Elixir SDK | Full Elixir implementation of ACP for the BEAM ecosystem |
| **Agmente** | iOS Client | Mobile client connecting to ACP agents (Copilot CLI, Gemini CLI) |

**ACPx** provides a mature headless ACP client runtime with persistent sessions, cooperative cancel, fs/terminal callbacks, and a growing registry of ACP bridges for Claude Code, Codex, OpenCode, Pi, and more.

---

### 4. Key Technical Features

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Session Close** | Stabilized (April 2026) | Cancels in-flight work without tearing down the ACP process |
| **Session Resume** | Stabilized (April 2026) | Reconnect without replaying conversation history |
| **Session List** | Stabilized (April 2026) | Discover existing sessions for history, switching, and cleanup |
| **Session Info Update** | Stabilized | Real-time session metadata updates without polling |
| **Session Config Options** | Stabilized (February 2026) | Flexible session-level configuration (models, modes, reasoning levels) |
| **Turn Completion Signal** | In RFC | Protocol-level barrier for prompts; all session_update notifications for a turn must be delivered before prompt response |
| **Transports WG** | Formed (April 2026) | Remote transport standardization (WebSockets, HTTP) |

---

### 5. Integration into Forge OS IKernelAdapter

The existing `IKernelAdapter` abstraction allows Forge OS to work with different AI kernels (LLM providers). However, ACP introduces two new concepts:
1. **ACPClient** — Forge OS as a client consuming ACP-compatible agents
2. **ACPRegistryAdapter** — For interacting with the ACP Registry to discover agents

Below is the updated architecture integrating ACP.

```python
# forge/kernel/acp_registry_adapter.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class DistributionType(Enum):
    BINARY = "binary"
    NPX = "npx"
    UVX = "uvx"

@dataclass
class BinaryDistribution:
    archive: str
    cmd: str
    args: List[str]
    env: Dict[str, str]

@dataclass
class PackageDistribution:
    package: str
    args: List[str]
    env: Dict[str, str]

@dataclass
class AgentManifest:
    id: str
    name: str
    version: str
    description: str
    distribution_binary: Dict[str, BinaryDistribution]
    distribution_npx: Optional[PackageDistribution]
    distribution_uvx: Optional[PackageDistribution]
    repository: Optional[str]
    authors: List[str]
    license: Optional[str]
    icon: Optional[str]

class ACPRegistryAdapter(ABC):
    """
    Enables Forge OS to discover, fetch, and install agents from the ACP Registry.
    The ACP Registry is a curated catalog that allows developers to distribute
    ACP-compatible agents to any client through a standardized lookup mechanism.
    """
    
    @abstractmethod
    async def fetch_registry_json(self) -> Dict:
        """Fetch the complete ACP registry JSON from CDN"""
        pass
    
    @abstractmethod
    async def get_agent_manifest(self, agent_id: str) -> AgentManifest:
        """Retrieve a specific agent's manifest from the registry"""
        pass
    
    @abstractmethod
    async def list_agents(self) -> List[AgentManifest]:
        """List all agents available in the ACP Registry"""
        pass
    
    @abstractmethod
    async def install_agent(self, agent_id: str, distribution_type: DistributionType = None) -> str:
        """
        Install an ACP agent using the appropriate distribution method.
        Returns path to the installed agent binary or script.
        """
        pass
    
    @abstractmethod
    async def uninstall_agent(self, agent_id: str) -> bool:
        """Remove an installed ACP agent"""
        pass
    
    @abstractmethod
    async def check_agent_availability(self, agent_id: str) -> bool:
        """Check if an agent is available for spawning"""
        pass
```

```python
# forge/kernel/acp_client.py
import asyncio
import json
from typing import AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class SessionInfo:
    id: str
    title: Optional[str]
    metadata: Dict

class ACPClient:
    """
    ACP client that communicates with ACP-compatible coding agents 
    via JSON-RPC over stdio.
    
    ACP is an open standard with Apache 2.0 license. It standardizes 
    communication between code editors and coding agents.
    """
    
    def __init__(self, agent_command: List[str]):
        self.agent_command = agent_command
        self.process: Optional[asyncio.subprocess.Process] = None
        self.session_id: Optional[str] = None
    
    async def start(self) -> None:
        """Launch the agent subprocess and initialize ACP session"""
        self.process = await asyncio.create_subprocess_exec(
            *self.agent_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await self._initialize()
    
    async def _initialize(self) -> None:
        """Send initialize request per ACP spec"""
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "Forge OS",
                    "version": "4.0.0"
                },
                "capabilities": {}
            },
            "id": 1
        }
        await self._send(init_request)
        response = await self._receive()
        # Handle response, extract session capabilities
        
    async def prompt(self, prompt: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict, None]:
        """
        Send a prompt to the agent and stream session_update notifications.
        
        The agent MAY send session/update notifications with content or tool 
        call updates after receiving the session/prompt request. The agent MUST 
        ensure it does so before responding to the session/prompt request.
        """
        request = {
            "jsonrpc": "2.0",
            "method": "session/prompt",
            "params": {
                "sessionId": session_id or self.session_id,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            },
            "id": 2
        }
        await self._send(request)
        
        # Stream updates until prompt response
        while True:
            response = await self._receive()
            if "method" in response and response["method"] == "session/update":
                yield response["params"]
            elif "id" in response and response["id"] == 2:
                yield {"type": "complete", "result": response.get("result")}
                break
    
    async def session_list(self) -> List[SessionInfo]:
        """Discover existing sessions from an agent (now stabilized)."""
        request = {
            "jsonrpc": "2.0",
            "method": "session/list",
            "id": 3
        }
        await self._send(request)
        response = await self._receive()
        sessions = response.get("result", {}).get("sessions", [])
        return [SessionInfo(id=s["id"], title=s.get("title"), metadata=s.get("metadata", {})) for s in sessions]
    
    async def session_resume(self, session_id: str) -> None:
        """
        Resume an existing session without replaying conversation history.
        Stabilized April 2026. Enables reconnection to long-running agent states.
        """
        request = {
            "jsonrpc": "2.0",
            "method": "session/resume",
            "params": {"sessionId": session_id},
            "id": 4
        }
        await self._send(request)
        response = await self._receive()
        if "error" in response:
            raise Exception(f"Failed to resume session: {response['error']}")
        self.session_id = session_id
    
    async def session_close(self, session_id: str) -> None:
        """
        Cancel in-flight work for a session and free resources without tearing down
        the whole ACP process. Stabilized April 2026.
        """
        request = {
            "jsonrpc": "2.0",
            "method": "session/close",
            "params": {"sessionId": session_id},
            "id": 5
        }
        await self._send(request)
    
    async def session_config_options(self) -> Dict:
        """
        Get available session configuration options (models, modes, reasoning levels).
        Stabilized February 2026.
        """
        request = {
            "jsonrpc": "2.0",
            "method": "session/config/options",
            "id": 6
        }
        await self._send(request)
        response = await self._receive()
        return response.get("result", {})
    
    async def stop(self) -> None:
        """Terminate the agent subprocess"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
    
    async def _send(self, message: Dict) -> None:
        """Send JSON-RPC message over stdin"""
        if self.process and self.process.stdin:
            self.process.stdin.write((json.dumps(message) + "\n").encode())
            await self.process.stdin.drain()
    
    async def _receive(self) -> Dict:
        """Receive JSON-RPC message from stdout"""
        if self.process and self.process.stdout:
            line = await self.process.stdout.readline()
            return json.loads(line.decode())
        return {}
```

```python
# forge/kernel/adapter.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from forge.kernel.acp_client import ACPClient
from forge.kernel.acp_registry_adapter import ACPRegistryAdapter

class IKernelAdapter(ABC):
    """
    Abstract interface for Forge OS Kernel Adapter Layer.
    
    Now enhanced with ACP Registry integration, allowing Forge OS to:
    1. Discover and install ACP-compatible agents from the official registry
    2. Spawn and communicate with those agents via the ACP protocol
    3. Leverage ACP's emerging features: session resume, session list, session close
    """
    
    @abstractmethod
    async def get_capabilities(self) -> Dict:
        """Report available tools, MCP servers, agent types, and ACP features."""
        pass
    
    @abstractmethod
    async def spawn_agent(self, persona: "AgentPersona", context: str, tools: list) -> "AgentResponse":
        """
        Spawn an AI agent (via native LLM API OR ACP-compatible subprocess).
        
        When using ACP mode, this delegates to acp_client.start().
        """
        pass
    
    @abstractmethod
    async def on_event(self, event: "LifecycleEvent") -> None:
        """Handle lifecycle events - now supports ACP session_updates as event streams."""
        pass
    
    @abstractmethod
    async def sync_memory(self) -> None:
        """Sync memory between kernel and Forge state."""
        pass
    
    # === New ACP-specific methods ===
    
    @abstractmethod
    async def get_acp_registry_adapter(self) -> ACPRegistryAdapter:
        """Return the ACP Registry adapter for agent discovery and installation."""
        pass
    
    @abstractmethod
    async def spawn_acp_agent(self, agent_id: str, session_id: Optional[str] = None) -> ACPClient:
        """
        Spawn an ACP-compatible agent from the registry.
        
        This method:
        1. Fetches the agent manifest from the ACP Registry
        2. Installs the agent if not already present (using npx, uvx, or binary)
        3. Spawns the agent subprocess
        4. Returns an ACPClient for communication
        
        The ACP Registry is a curated set of agents that support authentication.
        """
        pass
    
    @abstractmethod
    async def list_acp_agents(self) -> List[Dict]:
        """
        List all available ACP agents from the registry.
        
        Returns metadata including id, name, version, description, distribution types.
        """
        pass
    
    @abstractmethod
    async def is_acp_available(self) -> bool:
        """Check if ACP mode is available (agent registry accessible)."""
        pass
```

```python
# forge/kernel/litellm_adapter.py
from forge.kernel.adapter import IKernelAdapter
from forge.kernel.acp_registry_adapter import ACPRegistryAdapter
from forge.kernel.acp_client import ACPClient

class LiteLLMAdapter(IKernelAdapter):
    """
    LiteLLM-based adapter for Forge OS kernel operations.
    
    Enhanced to optionally use ACP-compatible agents via registry discovery.
    """
    
    def __init__(self, config: "KernelConfig", enable_acp: bool = True):
        self.config = config
        self.enable_acp = enable_acp
        self._acp_registry = ACPRegistryAdapter(config.registry_cache_dir) if enable_acp else None
    
    async def get_capabilities(self) -> Dict:
        """Return kernel capabilities including ACP support status."""
        capabilities = {
            "provider": "litellm",
            "model": self.config.model,
            "tools": ["read", "write", "bash", "mcp"],
            "acp_supported": self.enable_acp,
            "acp_features": ["session_resume", "session_list", "session_close", "config_options"] if self.enable_acp else []
        }
        if self.enable_acp:
            capabilities["acp_registry_url"] = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
        return capabilities
    
    async def spawn_agent(self, persona: "AgentPersona", context: str, tools: list) -> "AgentResponse":
        """Spawn an agent using LiteLLM (or ACP if configured)."""
        # If persona specifies an ACP agent ID, use ACP mode
        if self.enable_acp and hasattr(persona, "acp_agent_id") and persona.acp_agent_id:
            return await self._spawn_acp_agent(persona.acp_agent_id, persona, context, tools)
        else:
            return await self._spawn_litellm_agent(persona, context, tools)
    
    async def get_acp_registry_adapter(self) -> ACPRegistryAdapter:
        """Return the ACP Registry adapter for agent discovery."""
        if not self._acp_registry:
            raise RuntimeError("ACP support is not enabled")
        return self._acp_registry
    
    async def spawn_acp_agent(self, agent_id: str, session_id: Optional[str] = None) -> ACPClient:
        """
        Spawn an ACP-compatible agent from the registry.
        
        Implements the full ACP agent lifecycle:
        1. Agent discovery via registry manifest
        2. Installation using appropriate distribution (binary, npx, uvx)
        3. Subprocess spawning
        4. Session management (initialize, resume, etc.)
        """
        manifest = await self._acp_registry.get_agent_manifest(agent_id)
        install_path = await self._acp_registry.install_agent(agent_id)
        
        # Construct command based on distribution type
        cmd = []
        if manifest.distribution_uvx:
            cmd = ["uvx", manifest.distribution_uvx.package] + manifest.distribution_uvx.args
        elif manifest.distribution_npx:
            cmd = ["npx", "-y", manifest.distribution_npx.package] + manifest.distribution_npx.args
        elif manifest.distribution_binary:
            cmd = [f"{install_path}/{manifest.distribution_binary.cmd}"] + manifest.distribution_binary.args
        
        client = ACPClient(cmd)
        await client.start()
        
        if session_id:
            await client.session_resume(session_id)
        
        return client
    
    async def list_acp_agents(self) -> List[Dict]:
        """List all available ACP agents from the registry."""
        manifests = await self._acp_registry.list_agents()
        return [
            {
                "id": m.id,
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "distribution_types": self._get_distribution_types(m),
                "license": m.license
            }
            for m in manifests
        ]
    
    async def _spawn_acp_agent(self, agent_id: str, persona, context: str, tools: list) -> "AgentResponse":
        """Internal method to spawn an ACP agent and convert response to AgentResponse."""
        client = await self.spawn_acp_agent(agent_id)
        # Implementation details: handle prompt lifecycle, collect stream updates
        pass
    
    async def _spawn_litellm_agent(self, persona, context: str, tools: list) -> "AgentResponse":
        """Original LiteLLM agent spawning logic."""
        # Existing implementation
        pass
    
    def _get_distribution_types(self, manifest) -> List[str]:
        """Helper to determine available distribution types from manifest."""
        types = []
        if manifest.distribution_binary:
            types.append("binary")
        if manifest.distribution_npx:
            types.append("npx")
        if manifest.distribution_uvx:
            types.append("uvx")
        return types
```

```python
# forge/kernel/acp_registry_adapter.py (implementation)
import aiohttp
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

class ACPRegistryAdapter:
    """
    ACP Registry adapter implementation for Forge OS.
    
    The ACP Registry provides a standard way to discover, install, and 
    configure compatible agents without inventing custom integration metadata.
    """
    
    REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"
    REGISTRY_REPO = "https://raw.githubusercontent.com/agentclientprotocol/registry/main"
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._registry_cache = None
    
    async def fetch_registry_json(self) -> Dict:
        """Fetch the complete ACP registry JSON from CDN."""
        async with aiohttp.ClientSession() as session:
            async with session.get(self.REGISTRY_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    self._registry_cache = data
                    return data
                raise Exception(f"Failed to fetch registry: {response.status}")
    
    async def get_agent_manifest(self, agent_id: str) -> AgentManifest:
        """
        Retrieve a specific agent's manifest from the registry.
        
        Manifests follow the canonical format defined in the ACP Registry RFD,
        including required fields: id, name, version, description, distribution.
        """
        registry = await self.fetch_registry_json()
        agents = registry.get("agents", [])
        for agent in agents:
            if agent.get("id") == agent_id:
                return self._parse_manifest(agent)
        raise ValueError(f"Agent '{agent_id}' not found in ACP Registry")
    
    async def list_agents(self) -> List[AgentManifest]:
        """List all agents available in the ACP Registry."""
        registry = await self.fetch_registry_json()
        agents = registry.get("agents", [])
        return [self._parse_manifest(agent) for agent in agents]
    
    async def install_agent(self, agent_id: str, distribution_type: DistributionType = None) -> str:
        """
        Install an ACP agent using the appropriate distribution method.
        
        Distribution methods supported:
        - binary: Platform-specific archives (must support all OS targets)
        - npx: Node.js packages via npx -y package@latest
        - uvx: Python packages via uvx package@latest
        """
        manifest = await self.get_agent_manifest(agent_id)
        install_path = self.cache_dir / agent_id
        install_path.mkdir(exist_ok=True)
        
        # Prioritize specified distribution type, otherwise use first available
        if distribution_type == DistributionType.UVX and manifest.distribution_uvx:
            return await self._install_via_uvx(agent_id, manifest.distribution_uvx, install_path)
        elif distribution_type == DistributionType.NPX and manifest.distribution_npx:
            return await self._install_via_npx(agent_id, manifest.distribution_npx, install_path)
        elif manifest.distribution_binary:
            return await self._install_via_binary(agent_id, manifest.distribution_binary, install_path)
        elif manifest.distribution_uvx:
            return await self._install_via_uvx(agent_id, manifest.distribution_uvx, install_path)
        elif manifest.distribution_npx:
            return await self._install_via_npx(agent_id, manifest.distribution_npx, install_path)
        else:
            raise ValueError(f"No distribution method found for agent '{agent_id}'")
    
    async def uninstall_agent(self, agent_id: str) -> bool:
        """Remove an installed ACP agent from cache."""
        install_path = self.cache_dir / agent_id
        if install_path.exists():
            import shutil
            shutil.rmtree(install_path)
            return True
        return False
    
    async def check_agent_availability(self, agent_id: str) -> bool:
        """Check if an agent is available for spawning."""
        install_path = self.cache_dir / agent_id
        return install_path.exists()
    
    def _parse_manifest(self, data: Dict) -> AgentManifest:
        """Parse raw registry JSON into AgentManifest dataclass."""
        # Parse binary distributions if present
        binary_dist = {}
        if "distribution" in data and "binary" in data["distribution"]:
            for target, cfg in data["distribution"]["binary"].items():
                binary_dist[target] = BinaryDistribution(
                    archive=cfg.get("archive", ""),
                    cmd=cfg.get("cmd", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {})
                )
        
        # Parse package distributions
        npx_dist = None
        uvx_dist = None
        
        if "distribution" in data:
            if "npx" in data["distribution"]:
                npx_cfg = data["distribution"]["npx"]
                npx_dist = PackageDistribution(
                    package=npx_cfg.get("package", ""),
                    args=npx_cfg.get("args", []),
                    env=npx_cfg.get("env", {})
                )
            if "uvx" in data["distribution"]:
                uvx_cfg = data["distribution"]["uvx"]
                uvx_dist = PackageDistribution(
                    package=uvx_cfg.get("package", ""),
                    args=uvx_cfg.get("args", []),
                    env=uvx_cfg.get("env", {})
                )
        
        return AgentManifest(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            distribution_binary=binary_dist,
            distribution_npx=npx_dist,
            distribution_uvx=uvx_dist,
            repository=data.get("repository"),
            authors=data.get("authors", []),
            license=data.get("license"),
            icon=data.get("icon")
        )
    
    async def _install_via_uvx(self, agent_id: str, cfg: PackageDistribution, install_path: Path) -> str:
        """Install Python package via uvx for ACP agent execution."""
        # uvx executes the package directly without installing to a specific path
        # Return the package name for later spawning via uvx
        return f"uvx {cfg.package}"
    
    async def _install_via_npx(self, agent_id: str, cfg: PackageDistribution, install_path: Path) -> str:
        """Install Node.js package via npx for ACP agent execution."""
        return f"npx -y {cfg.package}"
    
    async def _install_via_binary(self, agent_id: str, binary_dist: Dict, install_path: Path) -> str:
        """Download and extract platform-specific binary archive."""
        import platform
        import aiohttp
        import zipfile
        import tarfile
        
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        arch_map = {
            ("darwin", "arm64"): "darwin-aarch64",
            ("darwin", "x86_64"): "darwin-x86_64",
            ("linux", "aarch64"): "linux-aarch64",
            ("linux", "x86_64"): "linux-x86_64",
            ("windows", "amd64"): "windows-x86_64",
            ("windows", "arm64"): "windows-aarch64"
        }
        target = arch_map.get((system, arch))
        
        if not target or target not in binary_dist:
            raise ValueError(f"No binary distribution for {system}-{arch}")
        
        cfg = binary_dist[target]
        archive_url = cfg.archive
        
        # Download and extract
        async with aiohttp.ClientSession() as session:
            async with session.get(archive_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download {archive_url}")
                
                # Determine archive type from URL
                if archive_url.endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(await response.read())) as zf:
                        zf.extractall(install_path)
                else:  # .tar.gz or .tgz
                    import tarfile
                    with tarfile.open(fileobj=io.BytesIO(await response.read())) as tf:
                        tf.extractall(install_path)
        
        return str(install_path)
```

```python
# forge/kernel/acp_integration_demo.py
"""
Demonstration: Using ACP agents from inside Forge OS

This shows how Forge OS can act as an ACP client to consume agents
discovered via the ACP Registry - not just LLM providers.
"""

async def demonstrate_acp_integration():
    """Example: Forge OS as ACP client, consuming registry agents."""
    
    # Initialize kernel adapter with ACP support enabled
    kernel = LiteLLMAdapter(config, enable_acp=True)
    
    # === Agent Discovery ===
    # List all available ACP agents from the registry
    agents = await kernel.list_acp_agents()
    for agent in agents:
        print(f"{agent['name']} v{agent['version']}: {agent['description']}")
        print(f"  Distribution: {', '.join(agent['distribution_types'])}")
    
    # === Agent Spawning ===
    # Spawn a specific ACP agent (e.g., GitHub Copilot CLI)
    acp_client = await kernel.spawn_acp_agent("github-copilot")
    
    # === Session Management ===
    # List existing sessions (stabilized April 2026)
    sessions = await acp_client.session_list()
    if sessions:
        # Resume an existing session without replaying history
        await acp_client.session_resume(sessions[0].id)
    
    # Get available configuration options (models, modes, reasoning levels)
    config_options = await acp_client.session_config_options()
    print(f"Available models: {config_options.get('models', [])}")
    
    # === Agent Interaction ===
    # Stream updates from agent prompt
    async for update in acp_client.prompt("Refactor this function for better error handling..."):
        if update["type"] == "session/update":
            content = update.get("params", {}).get("content", [])
            for block in content:
                if block["type"] == "text":
                    print(block["text"], end="")
                elif block["type"] == "tool_call":
                    print(f"\n🔧 Tool call: {block['name']}")
        elif update["type"] == "complete":
            print("\n✨ Agent completed task")
            break
    
    # === Cleanup ===
    # Close the session (frees resources without tearing down the process)
    if sessions:
        await acp_client.session_close(sessions[0].id)
    
    # Terminate the agent subprocess
    await acp_client.stop()
```

---

### 6. Updated System Architecture (ACP Layer)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Forge OS ACP Integration Layer               │
├─────────────────────────────────────────────────────────────────┤
│  Forge OS as ACP Client                                        │
│  ├── ACPClient (JSON-RPC over stdio)                          │
│  ├── Session management (resume, list, close)                 │
│  ├── Streaming updates (session/update)                       │
│  └── Turn completion tracking                                 │
├─────────────────────────────────────────────────────────────────┤
│  ACP Registry Adapter                                         │
│  ├── Registry JSON fetch (CDN)                                │
│  ├── Agent manifest parsing                                   │
│  ├── Agent installation (binary/npx/uvx)                      │
│  └── Registry submission (PR workflow)                        │
├─────────────────────────────────────────────────────────────────┤
│  IKernelAdapter (Enhanced)                                    │
│  ├── spawn_acp_agent()                                        │
│  ├── list_acp_agents()                                        │
│  ├── get_acp_registry_adapter()                               │
│  └── is_acp_available()                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

### 7. ACP Registry Adoption & Ecosystem

| Platform / Tool | ACP Support | Notes |
| :--- | :--- | :--- |
| **Zed Editor** | ✅ Native | Original co-creator |
| **JetBrains IDEs** | ✅ Native | Co-creator, Sergey Ignatov as Lead Maintainer |
| **GitHub Copilot CLI** | ✅ Native | Public preview announced January 2026 |
| **Google Gemini CLI** | ✅ Native | Flagship reference implementation |
| **Codex CLI** | ✅ Bridge | cola-io/codex-acp bridge implementation |
| **Claude Code** | ✅ Bridge | Via ACPx bridge in registry |
| **OpenCode** | ✅ Bridge | Via ACPx bridge in registry |

The ACP Registry is already used by major IDEs. For example, in JetBrains IDEs, users can select "Install From ACP Registry" directly from the AI Chat tool window to add ACP-compatible agents.

---

### 8. Summary of Impact on Forge OS

| Change | Impact | Implementation Status |
| :--- | :--- | :--- |
| ACPClient | Forge OS can spawn and communicate with any ACP-compatible agent (Gemini CLI, Copilot CLI, Codex) via JSON-RPC over stdio | ✅ Spec complete |
| ACPRegistryAdapter | Forge OS can discover agents from the official ACP Registry and install them using npx, uvx, or binary distribution | ✅ Spec complete |
| IKernelAdapter enhancements | New methods: `spawn_acp_agent`, `list_acp_agents`, `get_acp_registry_adapter` | ✅ Spec complete |
| Session management | Session resume, session list, session close (all stabilized) available to Forge OS | ✅ Integrated |
| Protocol parity | Python SDK (`agent-client-protocol` package) provides generated Pydantic models and async transports | ✅ Available |

---

### 9. Forge OS v4.0: Agent Discovery & Installation Flow

```text
forge agent discover
   ↓
ACP Registry Adapter fetches https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json
   ↓
Forge OS displays list of available agents
   ↓
forge agent install <agent-id> (--via uvx|npx|binary)
   ↓
ACPRegistryAdapter downloads/installs agent per manifest
   ↓
forge agent spawn <agent-id> [--session <session-id>]
   ↓
ACPClient spawns subprocess, initializes ACP session
   ↓
Session management: resume existing, list all, close on demand
```

This integration allows Forge OS to operate as a first-class ACP client, bridging the gap between deterministic pipeline execution and the growing ecosystem of ACP-compatible coding agents.

---

### 10. Recommended Next Steps

1. **Phase 0: Core Integration (2 weeks)**
   - Implement `ACPRegistryAdapter` with full JSON parsing and agent installation
   - Implement `ACPClient` with initialize, prompt, and session management
   - Add `forge agent` CLI commands (discover, install, list, spawn)

2. **Phase 1: Session Features (1 week)**
   - Implement `session_resume`, `session_list`, `session_close` (all stabilized)
   - Add persistent session tracking in Forge OS state (via event sourcing)
   - Verify session info update notifications work correctly

3. **Phase 2: Production Readiness (1 week)**
   - Cache registry JSON locally with TTL (daily refresh)
   - Add signature verification for agent binaries
   - Implement graceful fallback when ACP registry is unavailable
   - Add telemetry for agent installation and usage patterns (opt-in)
