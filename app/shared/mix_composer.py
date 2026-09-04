"""Interactive DJ mix-composer session state.

Sessions are deliberately ephemeral: the user edits a candidate chain, previews
transitions, and only the final action persists a set version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from uuid import uuid4


@dataclass
class MixSession:
    session_id: str
    track_ids: list[int]
    created_at: float = field(default_factory=monotonic)
    touched_at: float = field(default_factory=monotonic)
    transition: dict[str, object] = field(default_factory=dict)
    preview_job_id: str | None = None
    preview_path: str | None = None
    set_id: int | None = None
    candidates_by_source: dict[int, list[dict[str, object]]] = field(default_factory=dict)
    candidate_job_id: str | None = None
    candidate_error: str | None = None

    def touch(self) -> None:
        self.touched_at = monotonic()


class MixSessionRegistry:
    def __init__(self, *, max_sessions: int = 32, ttl_s: int = 6 * 3600) -> None:
        self._max_sessions = max_sessions
        self._ttl_s = ttl_s
        self._sessions: dict[str, MixSession] = {}
        self._lock = Lock()

    def create(self, first_track_id: int, set_id: int | None = None) -> MixSession:
        with self._lock:
            self._purge_locked()
            if len(self._sessions) >= self._max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.touched_at)
                self._sessions.pop(oldest.session_id, None)
            session = MixSession(uuid4().hex[:12], [int(first_track_id)], set_id=set_id)
            self._sessions[session.session_id] = session
            return session

    def get(self, session_id: str) -> MixSession | None:
        with self._lock:
            self._purge_locked()
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _purge_locked(self) -> None:
        cutoff = monotonic() - self._ttl_s
        for key, session in list(self._sessions.items()):
            if session.touched_at < cutoff:
                self._sessions.pop(key, None)


MIX_SESSIONS = MixSessionRegistry()
