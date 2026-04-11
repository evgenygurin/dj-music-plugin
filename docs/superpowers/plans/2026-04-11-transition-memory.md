# Transition Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every crossfade transition and use history to improve future set building.

**Architecture:** New `transition_history` table stores transition outcomes + user reactions. Repository + Service + MCP tools follow existing patterns (BaseRepository, Depends DI, @tool decorator). Panel auto-logs via server action after each crossfade. Scoring integration reads history to boost/penalize pairs.

**Tech Stack:** SQLAlchemy 2.0, Alembic, FastMCP, Pydantic v2, Next.js server actions, pytest + in-memory SQLite

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/db/models/transition_history.py` | CREATE | SQLAlchemy model |
| `app/db/repositories/transition_history.py` | CREATE | DB queries |
| `app/services/transition_history.py` | CREATE | Business logic |
| `app/schemas/transition_history.py` | CREATE | Pydantic DTOs |
| `app/controllers/tools/transition_history.py` | CREATE | 4 MCP tools |
| `app/controllers/dependencies/repos.py` | MODIFY | Add DI factory |
| `app/controllers/dependencies/services.py` | MODIFY | Add DI factory |
| `tests/conftest.py` | MODIFY | Import new model |
| `tests/test_repositories/test_transition_history.py` | CREATE | Repo tests |
| `tests/test_services/test_transition_history.py` | CREATE | Service tests |
| `panel/actions/transition-log-actions.ts` | CREATE | Server action |
| `panel/components/audio-player/audio-player-context.tsx` | MODIFY | Auto-log crossfades |

---

### Task 1: SQLAlchemy Model

**Files:**
- Create: `app/db/models/transition_history.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create the model file**

```python
# app/db/models/transition_history.py
"""Transition history — records every crossfade for learning."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin

class TransitionHistory(Base, TimestampMixin):
    """One row per crossfade transition played in the panel."""

    __tablename__ = "transition_history"
    __table_args__ = (
        UniqueConstraint(
            "from_track_id", "to_track_id", "session_id",
            name="uq_transition_history_pair_session",
        ),
        CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
            name="ck_transition_history_score",
        ),
        CheckConstraint(
            "user_reaction IS NULL OR user_reaction IN ('like', 'ban', 'skip', 'listened')",
            name="ck_transition_history_reaction",
        ),
        Index("idx_transition_history_from", "from_track_id"),
        Index("idx_transition_history_to", "to_track_id"),
        Index("idx_transition_history_score", "overall_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    to_track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    overall_score: Mapped[float | None] = mapped_column(default=None)
    bpm_score: Mapped[float | None] = mapped_column(default=None)
    harmonic_score: Mapped[float | None] = mapped_column(default=None)
    energy_score: Mapped[float | None] = mapped_column(default=None)
    spectral_score: Mapped[float | None] = mapped_column(default=None)
    groove_score: Mapped[float | None] = mapped_column(default=None)
    timbral_score: Mapped[float | None] = mapped_column(default=None)
    style: Mapped[str | None] = mapped_column(String(30), default=None)
    duration_sec: Mapped[float | None] = mapped_column(default=None)
    tempo_match_ratio: Mapped[float | None] = mapped_column(default=None)
    user_reaction: Mapped[str | None] = mapped_column(String(20), default=None)
    session_id: Mapped[str | None] = mapped_column(String(64), default=None)
```

- [ ] **Step 2: Import model in conftest.py**

Add to `tests/conftest.py` imports:
```python
from app.db.models.transition_history import TransitionHistory  # noqa: F401
```

- [ ] **Step 3: Verify model creates table in tests**

Run: `uv run pytest tests/conftest.py --co -q`
Expected: collector runs without import errors

- [ ] **Step 4: Commit**

```bash
git add app/db/models/transition_history.py tests/conftest.py
git commit -m "feat(db): add TransitionHistory model for transition memory"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Create: `app/schemas/transition_history.py`

- [ ] **Step 1: Create schema file**

```python
# app/schemas/transition_history.py
"""Pydantic DTOs for transition history."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class TransitionHistoryCreate(BaseModel):
    """Input for logging a transition."""
    from_track_id: int
    to_track_id: int
    overall_score: float | None = None
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
    user_reaction: str | None = None
    session_id: str | None = None

class TransitionHistoryRead(BaseModel):
    """Output for a transition history entry."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_track_id: int
    to_track_id: int
    overall_score: float | None
    bpm_score: float | None
    harmonic_score: float | None
    energy_score: float | None
    spectral_score: float | None
    groove_score: float | None
    timbral_score: float | None
    style: str | None
    duration_sec: float | None
    tempo_match_ratio: float | None
    user_reaction: str | None
    session_id: str | None
    created_at: datetime

class BestPairRead(BaseModel):
    """A historically-good partner for a track."""
    track_id: int
    play_count: int
    avg_score: float
    last_reaction: str | None
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from app.schemas.transition_history import TransitionHistoryRead; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```text
git add app/schemas/transition_history.py
git commit -m "feat(schemas): add TransitionHistory Pydantic DTOs"
```

---

### Task 3: Repository

**Files:**
- Create: `app/db/repositories/transition_history.py`
- Create: `tests/test_repositories/test_transition_history.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_repositories/test_transition_history.py
"""Tests for TransitionHistoryRepository."""

import pytest
from app.db.models.track import Track
from app.db.models.transition_history import TransitionHistory
from app.db.repositories.transition_history import TransitionHistoryRepository

@pytest.fixture
def repo(db_session):
    return TransitionHistoryRepository(db_session)

async def _seed_tracks(session, count=3):
    tracks = [Track(title=f"Track {i}", status=0) for i in range(count)]
    session.add_all(tracks)
    await session.flush()
    return tracks

@pytest.mark.asyncio
async def test_log_and_retrieve(repo, db_session):
    tracks = await _seed_tracks(db_session)
    entry = TransitionHistory(
        from_track_id=tracks[0].id,
        to_track_id=tracks[1].id,
        overall_score=0.85,
        style="swap",
        session_id="test-session-1",
    )
    saved = await repo.log(entry)
    assert saved.id is not None
    assert saved.overall_score == 0.85

    history = await repo.get_history(from_track_id=tracks[0].id, limit=10)
    assert len(history) == 1
    assert history[0].to_track_id == tracks[1].id

@pytest.mark.asyncio
async def test_best_pairs(repo, db_session):
    tracks = await _seed_tracks(db_session, 4)
    # Log 3 transitions from track 0
    for i, (to_idx, score, reaction) in enumerate([
        (1, 0.9, "like"),
        (2, 0.7, "listened"),
        (3, 0.3, "ban"),
    ]):
        entry = TransitionHistory(
            from_track_id=tracks[0].id,
            to_track_id=tracks[to_idx].id,
            overall_score=score,
            user_reaction=reaction,
            session_id=f"s{i}",
        )
        await repo.log(entry)

    pairs = await repo.get_best_pairs(tracks[0].id, limit=10)
    assert len(pairs) >= 2  # banned excluded
    assert pairs[0]["track_id"] == tracks[1].id  # highest score

@pytest.mark.asyncio
async def test_update_reaction(repo, db_session):
    tracks = await _seed_tracks(db_session)
    entry = TransitionHistory(
        from_track_id=tracks[0].id,
        to_track_id=tracks[1].id,
        overall_score=0.8,
        session_id="s1",
    )
    saved = await repo.log(entry)
    await repo.update_reaction(saved.id, "like")
    await db_session.flush()

    refreshed = await repo.get_by_id(saved.id)
    assert refreshed.user_reaction == "like"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repositories/test_transition_history.py -v`
Expected: ImportError — TransitionHistoryRepository not found

- [ ] **Step 3: Create repository**

```python
# app/db/repositories/transition_history.py
"""Transition history repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.transition_history import TransitionHistory
from app.db.repositories.base import BaseRepository

class TransitionHistoryRepository(BaseRepository[TransitionHistory]):
    """CRUD + analytics for transition history."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransitionHistory)

    async def log(self, entry: TransitionHistory) -> TransitionHistory:
        """Insert a new transition log entry."""
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_history(
        self,
        from_track_id: int | None = None,
        to_track_id: int | None = None,
        limit: int = 20,
        min_score: float | None = None,
    ) -> list[TransitionHistory]:
        """Query transition history with optional filters."""
        stmt = select(TransitionHistory).order_by(desc(TransitionHistory.created_at))
        if from_track_id is not None:
            stmt = stmt.where(TransitionHistory.from_track_id == from_track_id)
        if to_track_id is not None:
            stmt = stmt.where(TransitionHistory.to_track_id == to_track_id)
        if min_score is not None:
            stmt = stmt.where(TransitionHistory.overall_score >= min_score)
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_best_pairs(
        self, track_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Top-N best historical partners for a track, excluding banned."""
        stmt = (
            select(
                TransitionHistory.to_track_id.label("track_id"),
                func.count().label("play_count"),
                func.avg(TransitionHistory.overall_score).label("avg_score"),
                func.max(TransitionHistory.user_reaction).label("last_reaction"),
            )
            .where(TransitionHistory.from_track_id == track_id)
            .where(
                (TransitionHistory.user_reaction != "ban")
                | (TransitionHistory.user_reaction.is_(None))
            )
            .group_by(TransitionHistory.to_track_id)
            .order_by(desc("avg_score"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_pair_reaction(
        self, from_id: int, to_id: int
    ) -> str | None:
        """Get the most recent reaction for a specific pair."""
        stmt = (
            select(TransitionHistory.user_reaction)
            .where(TransitionHistory.from_track_id == from_id)
            .where(TransitionHistory.to_track_id == to_id)
            .where(TransitionHistory.user_reaction.isnot(None))
            .order_by(desc(TransitionHistory.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_reaction(self, entry_id: int, reaction: str) -> None:
        """Update the user_reaction on an existing entry."""
        entry = await self.get_by_id(entry_id)
        if entry is None:
            from app.core.errors import NotFoundError
            raise NotFoundError("TransitionHistory", entry_id)
        entry.user_reaction = reaction
        await self.session.flush()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_repositories/test_transition_history.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```text
git add app/db/repositories/transition_history.py tests/test_repositories/test_transition_history.py
git commit -m "feat(repo): add TransitionHistoryRepository with best_pairs query"
```

---

### Task 4: Service Layer

**Files:**
- Create: `app/services/transition_history.py`

- [ ] **Step 1: Create service**

```python
# app/services/transition_history.py
"""Transition history service — business logic for transition memory."""

from __future__ import annotations

from typing import Any

from app.db.models.transition_history import TransitionHistory
from app.db.repositories.transition_history import TransitionHistoryRepository

class TransitionHistoryService:
    """Records transitions and provides history-based recommendations."""

    HISTORY_LIKE_BOOST = 0.10
    HISTORY_BAN_REJECT = True
    HISTORY_SKIP_PENALTY = 0.15
    HISTORY_LISTENED_BOOST = 0.03

    def __init__(self, repo: TransitionHistoryRepository) -> None:
        self._repo = repo

    async def log_transition(
        self,
        from_track_id: int,
        to_track_id: int,
        overall_score: float | None = None,
        bpm_score: float | None = None,
        harmonic_score: float | None = None,
        energy_score: float | None = None,
        spectral_score: float | None = None,
        groove_score: float | None = None,
        timbral_score: float | None = None,
        style: str | None = None,
        duration_sec: float | None = None,
        tempo_match_ratio: float | None = None,
        user_reaction: str | None = None,
        session_id: str | None = None,
    ) -> TransitionHistory:
        """Record a completed transition."""
        entry = TransitionHistory(
            from_track_id=from_track_id,
            to_track_id=to_track_id,
            overall_score=overall_score,
            bpm_score=bpm_score,
            harmonic_score=harmonic_score,
            energy_score=energy_score,
            spectral_score=spectral_score,
            groove_score=groove_score,
            timbral_score=timbral_score,
            style=style,
            duration_sec=duration_sec,
            tempo_match_ratio=tempo_match_ratio,
            user_reaction=user_reaction,
            session_id=session_id,
        )
        return await self._repo.log(entry)

    async def get_history(
        self,
        from_track_id: int | None = None,
        to_track_id: int | None = None,
        limit: int = 20,
        min_score: float | None = None,
    ) -> list[TransitionHistory]:
        return await self._repo.get_history(from_track_id, to_track_id, limit, min_score)

    async def get_best_pairs(self, track_id: int, limit: int = 10) -> list[dict[str, Any]]:
        return await self._repo.get_best_pairs(track_id, limit)

    async def update_reaction(self, entry_id: int, reaction: str) -> None:
        valid = {"like", "ban", "skip", "listened"}
        if reaction not in valid:
            from app.core.errors import ValidationError
            raise ValidationError(f"Invalid reaction '{reaction}'. Must be one of: {', '.join(sorted(valid))}")
        await self._repo.update_reaction(entry_id, reaction)

    async def apply_history_bonus(self, from_id: int, to_id: int, base_score: float) -> float:
        """Adjust a transition score based on historical feedback."""
        reaction = await self._repo.get_pair_reaction(from_id, to_id)
        if reaction is None:
            return base_score
        if reaction == "like":
            return min(1.0, base_score + self.HISTORY_LIKE_BOOST)
        if reaction == "ban":
            return 0.0
        if reaction == "skip":
            return max(0.0, base_score - self.HISTORY_SKIP_PENALTY)
        if reaction == "listened":
            return min(1.0, base_score + self.HISTORY_LISTENED_BOOST)
        return base_score
```

- [ ] **Step 2: Verify import**

Run: `uv run python -c "from app.services.transition_history import TransitionHistoryService; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```text
git add app/services/transition_history.py
git commit -m "feat(service): add TransitionHistoryService with history bonus scoring"
```

---

### Task 5: DI Factories

**Files:**
- Modify: `app/controllers/dependencies/repos.py`
- Modify: `app/controllers/dependencies/services.py`

- [ ] **Step 1: Add repo factory**

Add to `app/controllers/dependencies/repos.py`:
```python
from app.db.repositories.transition_history import TransitionHistoryRepository

def get_transition_history_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> TransitionHistoryRepository:
    return TransitionHistoryRepository(session)
```

- [ ] **Step 2: Add service factory**

Add to `app/controllers/dependencies/services.py`:
```python
from app.db.repositories.transition_history import TransitionHistoryRepository
from app.services.transition_history import TransitionHistoryService

def get_transition_history_service(
    repo: TransitionHistoryRepository = Depends(get_transition_history_repo),  # noqa: B008
) -> TransitionHistoryService:
    return TransitionHistoryService(repo)
```

Import `get_transition_history_repo` from repos module at the top.

- [ ] **Step 3: Verify**

Run: `uv run python -c "from app.controllers.dependencies.repos import get_transition_history_repo; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```text
git add app/controllers/dependencies/repos.py app/controllers/dependencies/services.py
git commit -m "feat(di): add TransitionHistory DI factories"
```

---

### Task 6: MCP Tools

**Files:**
- Create: `app/controllers/tools/transition_history.py`

- [ ] **Step 1: Create tools file**

```python
# app/controllers/tools/transition_history.py
"""MCP tools — transition history (AI set builder memory)."""

from __future__ import annotations

from fastmcp import Context
from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.controllers.dependencies.services import get_transition_history_service
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from app.schemas.transition_history import BestPairRead, TransitionHistoryRead
from app.services.transition_history import TransitionHistoryService

@tool(tags={ToolCategory.CORE.value, "memory"})
@map_domain_errors
async def log_transition(
    from_track_id: int,
    to_track_id: int,
    overall_score: float | None = None,
    bpm_score: float | None = None,
    harmonic_score: float | None = None,
    energy_score: float | None = None,
    spectral_score: float | None = None,
    groove_score: float | None = None,
    timbral_score: float | None = None,
    style: str | None = None,
    duration_sec: float | None = None,
    tempo_match_ratio: float | None = None,
    user_reaction: str | None = None,
    session_id: str | None = None,
    svc: TransitionHistoryService = Depends(get_transition_history_service),
) -> TransitionHistoryRead:
    """Record a completed crossfade transition for learning.

    Called automatically by the panel after every crossfade.
    Scores and style come from the transition engine.
    """
    entry = await svc.log_transition(
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        overall_score=overall_score,
        bpm_score=bpm_score,
        harmonic_score=harmonic_score,
        energy_score=energy_score,
        spectral_score=spectral_score,
        groove_score=groove_score,
        timbral_score=timbral_score,
        style=style,
        duration_sec=duration_sec,
        tempo_match_ratio=tempo_match_ratio,
        user_reaction=user_reaction,
        session_id=session_id,
    )
    return TransitionHistoryRead.model_validate(entry)

@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_transition_history(
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    limit: int = 20,
    min_score: float | None = None,
    svc: TransitionHistoryService = Depends(get_transition_history_service),
) -> list[TransitionHistoryRead]:
    """Query past transitions with optional filters."""
    entries = await svc.get_history(from_track_id, to_track_id, limit, min_score)
    return [TransitionHistoryRead.model_validate(e) for e in entries]

@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_best_pairs(
    track_id: int,
    limit: int = 10,
    svc: TransitionHistoryService = Depends(get_transition_history_service),
) -> list[BestPairRead]:
    """Top-N best historical transition partners for a track.

    Returns tracks that scored well in past transitions, excluding banned pairs.
    Use this to inform suggest_next_track and build_set decisions.
    """
    pairs = await svc.get_best_pairs(track_id, limit)
    return [BestPairRead.model_validate(p) for p in pairs]

@tool(tags={ToolCategory.CORE.value, "memory"})
@map_domain_errors
async def update_reaction(
    entry_id: int,
    reaction: str,
    svc: TransitionHistoryService = Depends(get_transition_history_service),
) -> dict[str, str]:
    """Add user feedback (like/ban/skip/listened) to a transition.

    Args:
        entry_id: ID of the transition_history row.
        reaction: One of 'like', 'ban', 'skip', 'listened'.
    """
    await svc.update_reaction(entry_id, reaction)
    return {"status": "ok", "reaction": reaction}
```

- [ ] **Step 2: Verify tools register**

Run: `uv run python -c "from app.controllers.tools.transition_history import log_transition, get_best_pairs; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```text
git add app/controllers/tools/transition_history.py
git commit -m "feat(mcp): add transition memory tools — log, history, best_pairs, update_reaction"
```

---

### Task 7: Panel Server Action

**Files:**
- Create: `panel/actions/transition-log-actions.ts`

- [ ] **Step 1: Create server action**

```typescript
// panel/actions/transition-log-actions.ts
'use server'

import { callTool } from '@/lib/mcp-client'
import type { TransitionLog } from '@/components/audio-player/audio-player-types'

export async function logTransition(log: TransitionLog): Promise<{ id: number } | null> {
  const result = await callTool('log_transition', {
    from_track_id: log.from.id,
    to_track_id: log.to.id,
    overall_score: log.overallScore,
    bpm_score: null,
    harmonic_score: null,
    energy_score: null,
    spectral_score: null,
    groove_score: null,
    timbral_score: null,
    style: log.resolvedStyle,
    duration_sec: log.durationSec,
    tempo_match_ratio: log.tempoMatchRatio,
    user_reaction: null,
    session_id: null,
  })
  if (result.is_error) return null
  if (result.structured_content) return { id: (result.structured_content as { id: number }).id }
  return null
}

export async function updateTransitionReaction(
  entryId: number,
  reaction: 'like' | 'ban' | 'skip' | 'listened',
): Promise<boolean> {
  const result = await callTool('update_reaction', {
    entry_id: entryId,
    reaction,
  })
  return !result.is_error
}
```

- [ ] **Step 2: Commit**

```text
git add panel/actions/transition-log-actions.ts
git commit -m "feat(panel): add transition log server actions"
```

---

### Task 8: Panel Auto-Logging

**Files:**
- Modify: `panel/components/audio-player/audio-player-context.tsx`

- [ ] **Step 1: Find the transition log console.info**

Search for `[TRANSITION]` in audio-player-context.tsx. This is where `TransitionLog` is assembled and logged to console after each crossfade completes.

- [ ] **Step 2: Add server action call after console.info**

After the existing `console.info('[TRANSITION]', transitionLog)` line, add:

```typescript
// Persist to transition_history DB (fire-and-forget)
import('@/actions/transition-log-actions').then(mod => {
  void mod.logTransition(transitionLog)
}).catch(() => { /* non-fatal */ })
```

Use dynamic import to avoid adding the server action to the client bundle's critical path.

- [ ] **Step 3: Commit**

```text
git add panel/components/audio-player/audio-player-context.tsx
git commit -m "feat(player): auto-log every crossfade to transition_history DB"
```

---

### Task 9: Alembic Migration

**Files:**
- Create: `app/db/migrations/versions/xxx_add_transition_history.py`

- [ ] **Step 1: Generate migration**

Run: `uv run alembic revision --autogenerate -m "add transition_history table"`

- [ ] **Step 2: Review generated migration**

Verify it creates table `transition_history` with all columns, constraints, and indexes from Task 1.

- [ ] **Step 3: Apply migration**

Run: `uv run alembic upgrade head`
Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> ..., add transition_history table`

- [ ] **Step 4: Commit**

```text
git add app/db/migrations/
git commit -m "chore(db): add transition_history migration"
```

---

### Task 10: Integration — verify end-to-end

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/test_repositories/test_transition_history.py -v`
Expected: All PASS

- [ ] **Step 2: Verify MCP tool registration**

Run: `uv run python -c "
from app.controllers.tools.transition_history import log_transition, get_transition_history, get_best_pairs, update_reaction
print(f'log_transition: {log_transition.__name__}')
print(f'get_transition_history: {get_transition_history.__name__}')
print(f'get_best_pairs: {get_best_pairs.__name__}')
print(f'update_reaction: {update_reaction.__name__}')
print('All 4 tools OK')
"`
Expected: All 4 tools OK

- [ ] **Step 3: Run panel build check**

Run: `cd panel && ./node_modules/.bin/tsc --noEmit`
Expected: 0 errors

- [ ] **Step 4: Final commit**

```text
git commit --allow-empty -m "chore: verify transition memory end-to-end"
```
