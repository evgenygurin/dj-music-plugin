"""In-memory session state store.

Holds per-session data that resources expose under ``session://*``:

- The current set draft (tracks, template, duration target).
- A rolling tool-call history (last N calls).
- A rolling energy-samples ring buffer (for ``session://energy_trend``).

This is a pure data store — no business logic. The store is populated by
middleware (``AuditLogMiddleware`` writes tool history, specific tools
write draft updates) and read by resources.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

from app.v2.shared.time import utc_timestamp_iso


class InMemorySessionStore:
    """Single-process session state. Swap for Redis in Phase 5 if needed."""

    def __init__(
        self,
        *,
        energy_capacity: int = 50,
        tool_history_capacity: int = 100,
    ) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}
        self._tool_history: dict[str, deque[dict[str, Any]]] = {}
        self._energy: dict[str, deque[float]] = {}
        self._energy_cap = energy_capacity
        self._history_cap = tool_history_capacity
        self._lock = Lock()

    # ── Draft ────────────────────────────────────────────────────

    def _default_draft(self, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "tracks": [],
            "target_duration_ms": None,
            "template_name": None,
            "last_mutation_at": None,
        }

    def get_draft(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            d = self._drafts.get(session_id)
            if d is None:
                return self._default_draft(session_id)
            return dict(d)

    def update_draft(self, session_id: str, **fields: Any) -> None:
        with self._lock:
            d = self._drafts.setdefault(session_id, self._default_draft(session_id))
            d.update(fields)
            d["last_mutation_at"] = utc_timestamp_iso()

    # ── Tool history ─────────────────────────────────────────────

    def append_tool(self, session_id: str, *, tool: str, ok: bool, **extra: Any) -> None:
        with self._lock:
            q = self._tool_history.setdefault(session_id, deque(maxlen=self._history_cap))
            entry: dict[str, Any] = {
                "tool": tool,
                "ok": ok,
                "at": utc_timestamp_iso(),
            }
            entry.update(extra)
            q.append(entry)

    def get_tool_history(
        self, session_id: str, *, limit: int | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            q = self._tool_history.get(session_id, deque())
            data = list(q)
            if limit is not None:
                return data[-limit:]
            return data

    # ── Energy samples ───────────────────────────────────────────

    def append_energy(self, session_id: str, value: float) -> None:
        with self._lock:
            q = self._energy.setdefault(session_id, deque(maxlen=self._energy_cap))
            q.append(float(value))

    def get_energy_samples(self, session_id: str, *, last_n: int) -> list[float]:
        with self._lock:
            q = self._energy.get(session_id, deque())
            if last_n <= 0:
                return []
            return list(q)[-last_n:]
