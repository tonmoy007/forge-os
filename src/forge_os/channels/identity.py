"""Channel identity binding store (FR-CH-005), atomic + ``forge_dir``-injected.

Persists to ``<project_root>/.forge/channels/identities.json``. Project root is
injected by the caller (L001/L005); tests use ``tmp_path``. Never writes
canonical pipeline state.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from forge_os.channels.errors import ChannelAlreadyBoundError
from forge_os.schemas.channel import ChannelIdentity

IDENTITIES_RELPATH = Path(".forge") / "channels" / "identities.json"


class ChannelIdentityStore:
    """The set of channel sender -> Forge identity bindings for one project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.path = self.project_root / IDENTITIES_RELPATH

    def _load_all(self) -> list[ChannelIdentity]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [ChannelIdentity.model_validate(item) for item in raw]

    def get(self, channel_id: str, sender: str) -> ChannelIdentity | None:
        """Return the binding for (channel_id, sender), or ``None``."""
        return next(
            (
                identity
                for identity in self._load_all()
                if identity.channel_id == channel_id and identity.sender == sender
            ),
            None,
        )

    def is_bound(self, channel_id: str, sender: str) -> bool:
        """Whether (channel_id, sender) is bound to a Forge identity."""
        identity = self.get(channel_id, sender)
        return identity is not None and identity.bound

    def begin_pairing(self, channel_id: str, sender: str) -> str:
        """Start binding: store an unbound identity with a fresh pairing code.

        Refuses to re-pair an already-bound (channel, sender): a confirmed binding
        must be explicitly unbound first, so a re-pair cannot silently destroy it.
        """
        if self.is_bound(channel_id, sender):
            raise ChannelAlreadyBoundError(
                f"'{sender}' on '{channel_id}' is already bound; unbind before re-pairing"
            )
        code = uuid4().hex[:8]
        self._upsert(
            ChannelIdentity(
                channel_id=channel_id, sender=sender, bound=False, pairing_code=code
            )
        )
        return code

    def confirm(
        self, channel_id: str, sender: str, pairing_code: str, forge_identity: str
    ) -> bool:
        """HITL-confirm a pairing. Returns ``True`` if the code matched and bound."""
        identity = self.get(channel_id, sender)
        if (
            identity is None
            or identity.pairing_code is None
            or identity.pairing_code != pairing_code
        ):
            return False
        identity.bound = True
        identity.forge_identity = forge_identity
        identity.pairing_code = None
        self._upsert(identity)
        return True

    def _upsert(self, identity: ChannelIdentity) -> None:
        kept = [
            existing
            for existing in self._load_all()
            if not (
                existing.channel_id == identity.channel_id
                and existing.sender == identity.sender
            )
        ]
        kept.append(identity)
        self._write(kept)

    def _write(self, identities: list[ChannelIdentity]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [identity.model_dump(mode="json") for identity in identities], indent=2
        )
        handle, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(payload)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
