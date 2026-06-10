"""Phase 10 lazy context use cases (P10.15-19)."""

from __future__ import annotations

from pathlib import Path

from forge_os.context.lazy import LazyContextBuilder


class LazyContextUseCases:
    """Business logic facade for lazy context budgeting and skill expansion.

    Raises `forge_os.context.lazy.LazyContextError` on domain failures; the
    CLI translates it into user-facing output.
    """

    def __init__(self, project_root: Path, forge_dir: Path | None = None) -> None:
        self._builder = LazyContextBuilder(project_root, forge_dir=forge_dir)

    def budget(self, stage_id: str, *, token_budget: int = 2000) -> dict[str, object]:
        """Return the composed lazy context bundle with token accounting."""
        return self._builder.build(stage_id, token_budget=token_budget).model_dump()

    def lazy_stats(self, stage_id: str, *, token_budget: int = 2000) -> dict[str, object]:
        """Return eager vs lazy token savings for *stage_id*."""
        return self._builder.stats(stage_id, token_budget=token_budget)

    def expand(self, name: str) -> dict[str, object]:
        """Return the full skill record for one menu entry."""
        return self._builder.expand_skill(name)
