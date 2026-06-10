"""Phase 10 Dreamer — offline digests, lesson decay, and tension detection.

The Dreamer only PROPOSES: it never deletes lessons, never auto-approves,
and dormancy is always reversible via `LessonStore.revive`.
"""

from forge_os.dreamer.decay import apply_decay, decayed_confidence
from forge_os.dreamer.digest import DailyDigestWriter
from forge_os.dreamer.tensions import detect_tensions, reingest_reflections

__all__ = [
    "DailyDigestWriter",
    "apply_decay",
    "decayed_confidence",
    "detect_tensions",
    "reingest_reflections",
]
