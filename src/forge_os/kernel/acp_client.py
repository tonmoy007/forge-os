"""ACPClient — JSON-RPC 2.0 over stdio communication with ACP-compatible agents.

ACP (Agent Client Protocol) standardises communication between code editors
and AI coding agents via JSON-RPC over newline-delimited JSON on stdio.

Reference: https://github.com/agentclientprotocol/registry
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionInfo:
    """Metadata about an ACP session."""

    id: str
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ACPClientError(RuntimeError):
    """Raised when an ACP operation fails."""


class ACPClient:
    """Communicate with ACP-compatible coding agents via JSON-RPC over stdio.

    Usage:
        client = ACPClient(["npx", "@example/agent"])
        client.start()
        for update in client.prompt("Implement feature X"):
            print(update)
        client.stop()
    """

    def __init__(self, agent_command: list[str]) -> None:
        self.agent_command = agent_command
        self.process: subprocess.Popen | None = None
        self.session_id: str | None = None
        self._msg_id: int = 0
        self._server_info: dict[str, Any] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> dict[str, Any]:
        """Launch the agent subprocess and send initialize request.

        Returns the server capabilities from the initialize response.
        """
        self.process = subprocess.Popen(
            self.agent_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )
        return self._initialize()

    def stop(self) -> None:
        """Terminate the agent subprocess gracefully."""
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.process.kill()
            self.process.wait()
        finally:
            self.process = None

    # ── Core ACP Methods ───────────────────────────────────────────────────

    def _initialize(self) -> dict[str, Any]:
        """Send the ACP initialize request."""
        request = self._build_request("initialize", {
            "clientInfo": {"name": "Forge OS", "version": "0.5.0"},
            "capabilities": {},
        })
        self._send(request)
        response = self._receive()
        if "error" in response:
            msg = response["error"].get("message", "initialize failed")
            raise ACPClientError(f"ACP initialize failed: {msg}")
        result = response.get("result", {})
        self._server_info = result.get("serverInfo", {})
        # Some agents return a session ID directly from initialize
        self.session_id = result.get("sessionId")
        return result

    def prompt(
        self,
        prompt_text: str,
        session_id: str | None = None,
    ) -> Generator[dict[str, Any], None, dict[str, Any]]:
        """Send a prompt and yield streaming updates, then return the result.

        Yields session/update notification params as they arrive.
        Returns the final response result dict.
        """
        request = self._build_request("session/prompt", {
            "sessionId": session_id or self.session_id,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
            ],
        })
        self._send(request)

        final_result: dict[str, Any] = {}

        while True:
            response = self._receive()
            if response is None:
                raise ACPClientError("Connection closed before prompt response")

            # Streaming notification
            if response.get("method") == "session/update":
                yield response.get("params", {})
                continue

            # Final response to our prompt request
            if "id" in response and response["id"] == request["id"]:
                if "error" in response:
                    msg = response["error"].get("message", "unknown error")
                    raise ACPClientError(f"ACP prompt failed: {msg}")
                final_result = response.get("result", {})
                break

        return final_result

    def session_list(self) -> list[SessionInfo]:
        """Discover existing sessions from the agent.

        Stabilised April 2026.
        """
        request = self._build_request("session/list", {})
        self._send(request)
        response = self._receive()
        if "error" in response:
            msg = response["error"].get("message", "session list failed")
            raise ACPClientError(f"ACP session list failed: {msg}")
        sessions = response.get("result", {}).get("sessions", [])
        return [
            SessionInfo(
                id=s["id"],
                title=s.get("title"),
                metadata=s.get("metadata", {}),
            )
            for s in sessions
        ]

    def session_resume(self, session_id: str) -> None:
        """Resume an existing session without replaying conversation history.

        Stabilised April 2026.
        """
        request = self._build_request("session/resume", {
            "sessionId": session_id,
        })
        self._send(request)
        response = self._receive()
        if "error" in response:
            msg = response["error"].get("message", "resume failed")
            raise ACPClientError(f"ACP session resume failed: {msg}")
        self.session_id = session_id

    def session_close(self, session_id: str) -> None:
        """Cancel in-flight work for a session and free resources.

        Stabilised April 2026. Does not tear down the ACP process.
        """
        request = self._build_request("session/close", {
            "sessionId": session_id,
        })
        self._send(request)
        response = self._receive()
        if "error" in response:
            msg = response["error"].get("message", "close failed")
            raise ACPClientError(f"ACP session close failed: {msg}")

    def session_config_options(self) -> dict[str, Any]:
        """Query available models, modes, and reasoning levels.

        Stabilised February 2026.
        """
        request = self._build_request("session/config/options", {})
        self._send(request)
        response = self._receive()
        if "error" in response:
            msg = response["error"].get("message", "config options failed")
            raise ACPClientError(f"ACP config options failed: {msg}")
        return response.get("result", {})

    # ── Transport ──────────────────────────────────────────────────────────

    def _build_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._msg_id += 1
        return {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._msg_id,
        }

    def _send(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise ACPClientError("ACP process not running")
        line = json.dumps(message, ensure_ascii=False) + "\n"
        self.process.stdin.write(line)
        self.process.stdin.flush()

    def _receive(self) -> dict[str, Any] | None:
        if self.process is None or self.process.stdout is None:
            raise ACPClientError("ACP process not running")
        line = self.process.stdout.readline()
        if not line:
            return None
        return json.loads(line)

    # ── Utilities ──────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """Check if the ACP agent subprocess is still alive."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def wait_for_completion(self, timeout: float = 300.0) -> None:
        """Wait for the agent subprocess to finish.

        Used when the agent exits after completing its work.
        """
        if self.process is None:
            return
        deadline = time.monotonic() + timeout
        while self.is_running and time.monotonic() < deadline:
            time.sleep(0.1)
