"""Async HTTP utility module for Forge OS.

Provides retry, timeout, and error handling wrappers around aiohttp/httpx.
Phase 08.5 async infrastructure.
"""

from __future__ import annotations

import asyncio
from typing import Any


class AsyncHTTPError(RuntimeError):
    """Raised when an async HTTP operation fails."""


class AsyncHTTPClient:
    """Lightweight async HTTP client with retry and timeout.

    Uses httpx by default (lazy import) with aiohttp as fallback.
    """

    DEFAULT_TIMEOUT = 15
    MAX_RETRIES = 2

    def __init__(
        self,
        base_url: str = "",
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}
        if "User-Agent" not in self.headers:
            self.headers["User-Agent"] = "ForgeOS/0.5.0"

    async def get(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Perform an async GET request with retry logic."""
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str = "", **kwargs: Any) -> dict[str, Any]:
        """Perform an async POST request with retry logic."""
        return await self._request("POST", path, **kwargs)

    async def _request(self, method: str, path: str = "", **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}" if self.base_url else path
        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            try:
                return await self._try_request(method, url, **kwargs)
            except AsyncHTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    wait = 0.5 * (2**attempt)
                    await asyncio.sleep(wait)
                continue

        raise AsyncHTTPError(
            f"Request failed after {1 + self.max_retries} attempts: {last_error}"
        ) from last_error

    async def _try_request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=self.headers,
                    **kwargs,
                )
                resp.raise_for_status()
                return resp.json()
        except ImportError:
            return await self._request_via_aiohttp(method, url, **kwargs)
        except Exception as exc:
            raise AsyncHTTPError(str(exc)) from exc

    async def _request_via_aiohttp(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            import aiohttp

            async with aiohttp.ClientSession(
                headers=self.headers, timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.request(method, url, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as exc:
            raise AsyncHTTPError(str(exc)) from exc

    async def head(self, url: str) -> bool:
        """Check if a URL is reachable."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.head(url, headers=self.headers)
                return resp.is_success
        except Exception:  # noqa: BLE001
            return False
