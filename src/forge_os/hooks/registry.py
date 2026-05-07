"""In-process lifecycle hook registry."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass

from forge_os.events.model import LifecycleEvent

Hook = Callable[[LifecycleEvent], None]


@dataclass(frozen=True)
class HookResult:
    """Result of one hook invocation."""

    hook_name: str
    status: str
    error: str | None = None


@dataclass(frozen=True)
class RegisteredHook:
    """Registered hook metadata."""

    event_type: str
    name: str
    handler: Hook
    order: int
    timeout_seconds: float
    blocking: bool = False


class HookRegistry:
    """Register and run lifecycle hooks in deterministic order."""

    def __init__(self) -> None:
        self._hooks: list[RegisteredHook] = []

    def register(
        self,
        event_type: str,
        handler: Hook,
        *,
        name: str | None = None,
        order: int = 100,
        timeout_seconds: float = 5.0,
        blocking: bool = False,
    ) -> None:
        """Register a hook for an event type."""

        hook_name = name or getattr(handler, "__name__", "anonymous_hook")
        self._hooks.append(
            RegisteredHook(
                event_type=event_type,
                name=hook_name,
                handler=handler,
                order=order,
                timeout_seconds=timeout_seconds,
                blocking=blocking,
            )
        )

    def hooks_for(self, event_type: str) -> list[RegisteredHook]:
        """Return hooks for an event type in deterministic order."""

        return sorted(
            (hook for hook in self._hooks if hook.event_type == event_type),
            key=lambda hook: (hook.order, hook.name),
        )

    def run(self, event: LifecycleEvent) -> list[HookResult]:
        """Run hooks for an event, isolating non-blocking failures."""

        results: list[HookResult] = []
        for hook in self.hooks_for(event.event_type):
            result = self._run_one(hook, event)
            results.append(result)
            if hook.blocking and result.status != "succeeded":
                raise RuntimeError(f"Blocking hook `{hook.name}` failed: {result.error}")
        return results

    def _run_one(self, hook: RegisteredHook, event: LifecycleEvent) -> HookResult:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(hook.handler, event)
        try:
            _ = future.result(timeout=hook.timeout_seconds)
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return HookResult(hook_name=hook.name, status="timed_out", error="timeout")
        except Exception as exc:  # noqa: BLE001 - hook failures must be isolated
            executor.shutdown(wait=False, cancel_futures=True)
            return HookResult(hook_name=hook.name, status="failed", error=str(exc))
        executor.shutdown(wait=True)
        return HookResult(hook_name=hook.name, status="succeeded")
