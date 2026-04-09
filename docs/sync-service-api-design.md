# Sync Service API Design

> Дизайн интерфейсов для `PlaylistSyncService` и `SetPushService`.
> Только контракты -- без реализации.

---

## 1. Error Hierarchy

Новые ошибки в `app/core/errors.py`, наследуются от `DJMusicError`:

```text
DJMusicError
└── SyncError                         # базовая для всех sync-ошибок
    ├── SyncConflictError             # неразрешимый конфликт (трек удалён с одной стороны)
    ├── SyncRevisionMismatchError     # YM playlist revision устарела (concurrent edit)
    ├── SyncNoYMPlaylistError         # локальный плейлист не привязан к YM (нет platform_ids)
    ├── SyncTrackNotLinkedError       # трек не имеет yandex_track_id (нельзя push)
    └── SyncAbortedError              # пользователь отменил через elicitation
```

### Сигнатуры

```python
class SyncError(DJMusicError):
    """Base error for sync operations."""

class SyncConflictError(SyncError):
    """Unresolved sync conflict requiring user decision."""
    def __init__(
        self,
        track_id: int,
        conflict_type: str,     # "deleted_remote" | "deleted_local" | "modified"
        details: str,
    ) -> None: ...

class SyncRevisionMismatchError(SyncError):
    """YM playlist was modified externally between our read and write."""
    def __init__(self, playlist_id: int, expected_revision: int, actual_revision: int) -> None: ...

class SyncNoYMPlaylistError(SyncError):
    """Local playlist has no linked YM playlist."""
    def __init__(self, playlist_id: int) -> None: ...

class SyncTrackNotLinkedError(SyncError):
    """One or more tracks lack a yandex_track_id."""
    def __init__(self, track_ids: list[int]) -> None: ...

class SyncAbortedError(SyncError):
    """User aborted the sync via elicitation."""
```

**Обоснование**: каждый подкласс несёт достаточно контекста для MCP tool, чтобы сформировать понятный `ToolError`. `SyncConflictError` намеренно содержит `track_id` и тип конфликта -- tool-слой может использовать это для elicitation.

---

## 2. ProgressCallback Protocol

Decoupling от FastMCP `Context` -- сервис не знает о MCP:

```python
# app/core/progress.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class ProgressCallback(Protocol):
    """Interface for reporting progress from services.

    Adapters:
    - MCPProgressAdapter: wraps ctx.report_progress() + ctx.info()
    - NullProgress: no-op for tests and non-MCP callers
    """

    async def report_progress(self, current: int, total: int) -> None:
        """Report numeric progress (e.g., 3 of 10 tracks processed)."""
        ...

    async def info(self, message: str) -> None:
        """Report a human-readable status message."""
        ...

    async def warning(self, message: str) -> None:
        """Report a non-fatal issue (e.g., iCloud stub, missing features)."""
        ...
```

### Адаптеры (создаются в tool-слое, передаются в сервис):

```python
# app/controllers/adapters.py

class MCPProgressAdapter:
    """Wraps FastMCP Context into ProgressCallback."""
    def __init__(self, ctx: Context) -> None: ...
    async def report_progress(self, current: int, total: int) -> None: ...
    async def info(self, message: str) -> None: ...
    async def warning(self, message: str) -> None: ...

class NullProgress:
    """No-op implementation for tests and direct service calls."""
    async def report_progress(self, current: int, total: int) -> None: ...
    async def info(self, message: str) -> None: ...
    async def warning(self, message: str) -> None: ...
```

---

## 3. Sync Data Types

Pydantic-модели для возвращаемых значений (в `app/core/schemas.py` или `app/services/sync_types.py`):

```python
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel

class SyncDirection(StrEnum):
    PULL = "pull"         # YM -> local
    PUSH = "push"         # local -> YM
    BIDIRECTIONAL = "bidirectional"

class ConflictStrategy(StrEnum):
    SOURCE_WINS = "source_wins"   # source_of_truth побеждает
    ASK = "ask"                   # elicitation для каждого конфликта
    SKIP = "skip"                 # пропустить конфликтные треки

class PushMode(StrEnum):
    CREATE = "create"     # всегда новый YM-плейлист
    UPDATE = "update"     # обновить существующий
    AUTO = "auto"         # create если нет, update если есть

# ── Diff items ────────────────────────────────────

class SyncTrackAction(BaseModel):
    """Single track change detected during diff."""
    track_id: int
    title: str
    ym_track_id: str | None = None
    action: str              # "add" | "remove" | "reorder"
    side: str                # "local" | "remote"

class SyncConflict(BaseModel):
    """An unresolved conflict requiring a decision."""
    track_id: int
    title: str
    conflict_type: str       # "deleted_remote" | "deleted_local" | "in_active_set"
    resolution: str | None = None   # filled after resolution

# ── Result types ──────────────────────────────────

class SyncDiff(BaseModel):
    """Computed diff before applying changes (dry_run output)."""
    to_add_local: list[SyncTrackAction] = []
    to_remove_local: list[SyncTrackAction] = []
    to_add_remote: list[SyncTrackAction] = []
    to_remove_remote: list[SyncTrackAction] = []
    conflicts: list[SyncConflict] = []

class SyncResult(BaseModel):
    """Result of a completed sync operation."""
    playlist_id: int
    direction: SyncDirection
    dry_run: bool
    tracks_added: int = 0
    tracks_removed: int = 0
    conflicts_resolved: int = 0
    conflicts_skipped: int = 0
    diff: SyncDiff
    ym_revision: int | None = None   # updated YM revision after push

class SetPushResult(BaseModel):
    """Result of pushing a DJ set to YM."""
    set_id: int
    set_name: str
    ym_playlist_kind: int | None = None
    ym_playlist_title: str
    mode_used: PushMode              # actual mode applied
    tracks_pushed: int = 0
    tracks_skipped: int = 0          # tracks without ym_track_id
    skipped_track_ids: list[int] = []
    created_new: bool = False
```

---

## 4. PlaylistSyncService Interface

```python
# app/services/sync.py

class PlaylistSyncService:
    """Bidirectional playlist sync between local DB and Yandex Music.

    Сервис НЕ знает о MCP, FastMCP, Context.
    Все зависимости через __init__.
    """

    def __init__(
        self,
        playlist_repo: PlaylistRepository,
        track_repo: TrackRepository,
        ym_client: YandexMusicClient,
        progress: ProgressCallback | None = None,
    ) -> None: ...

    # ── Public API ────────────────────────────────────

    async def compute_diff(
        self,
        playlist_id: int,
        direction: SyncDirection,
    ) -> SyncDiff:
        """Compute the diff between local playlist and its YM counterpart.

        Steps:
        1. Load local playlist with items (PlaylistRepo.get_with_items)
        2. Parse platform_ids JSON -> extract YM owner_id:kind
        3. Fetch YM playlist tracks via YM client
        4. Build track_id <-> ym_track_id mapping (via YandexMetadata table)
        5. Compute added/removed/reordered per direction
        6. Detect conflicts (track in active set but deleted remotely, etc.)

        Raises:
            NotFoundError: playlist not found
            SyncNoYMPlaylistError: no YM playlist linked
            YandexMusicError: YM API failure

        Returns:
            SyncDiff with all detected changes and unresolved conflicts.
        """
        ...

    async def apply_sync(
        self,
        playlist_id: int,
        direction: SyncDirection,
        conflict_strategy: ConflictStrategy = ConflictStrategy.SOURCE_WINS,
        conflict_resolutions: dict[int, str] | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Apply sync changes for a playlist.

        Parameters:
            playlist_id: local playlist ID
            direction: pull/push/bidirectional
            conflict_strategy: how to handle conflicts by default
            conflict_resolutions: per-track override {track_id: "keep"|"remove"|"skip"}
                (populated by tool layer after elicitation when strategy=ASK)
            dry_run: if True, compute diff but don't apply

        Flow:
        1. compute_diff(playlist_id, direction)
        2. Resolve conflicts per strategy or per-track overrides
        3. If dry_run: return SyncResult with diff, applied=False
        4. PULL: create local tracks for new YM tracks, remove deleted ones
        5. PUSH: add_tracks_to_playlist / remove_tracks_from_playlist via YM client
        6. Re-fetch YM playlist for fresh revision
        7. Report progress throughout

        Raises:
            NotFoundError: playlist not found
            SyncNoYMPlaylistError: no YM playlist linked
            SyncConflictError: unresolved conflict when strategy != skip
            SyncRevisionMismatchError: YM revision changed mid-sync
            SyncTrackNotLinkedError: push requires ym_track_id on all tracks
            YandexMusicError: YM API failure

        Returns:
            SyncResult with counts and diff details.
        """
        ...

    async def get_ym_playlist_info(
        self,
        playlist_id: int,
    ) -> tuple[str, int]:
        """Extract YM (owner_id, kind) from local playlist's platform_ids.

        Raises:
            NotFoundError: playlist not found
            SyncNoYMPlaylistError: no YM link in platform_ids

        Returns:
            (owner_id, kind) tuple for YM API calls.
        """
        ...
```

### Обоснование решений

| Решение | Почему |
|---------|--------|
| `compute_diff` отделён от `apply_sync` | Tool может показать diff пользователю (dry_run), дать решить конфликты через elicitation, затем вызвать apply с `conflict_resolutions` |
| `conflict_resolutions: dict[int, str]` | Tool-слой собирает решения через `safe_elicit()` и передаёт bulk -- сервис не знает об elicitation |
| `progress: ProgressCallback | None` | Optional -- тесты не передают, tool-слой передаёт MCPProgressAdapter |
| Нет `session` в init | Сервис получает репозитории, которые уже держат session -- паттерн проекта |

---

## 5. SetPushService Interface

```python
# app/services/sync.py (в том же файле, общий домен)

class SetPushService:
    """Push a DJ set as a Yandex Music playlist.

    Сервис НЕ знает о MCP. Не импортирует FastMCP.
    """

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        ym_client: YandexMusicClient,
        progress: ProgressCallback | None = None,
    ) -> None: ...

    # ── Public API ────────────────────────────────────

    async def push(
        self,
        set_id: int,
        ym_playlist_name: str | None = None,
        mode: PushMode = PushMode.AUTO,
    ) -> SetPushResult:
        """Push the latest version of a DJ set to YM as a playlist.

        Parameters:
            set_id: DJ set ID
            ym_playlist_name: name for YM playlist (defaults to set.name)
            mode: CREATE always creates new; UPDATE requires existing
                  ym_playlist_id on DjSet; AUTO creates if missing, updates if present

        Flow:
        1. Load DjSet + latest SetVersion with items
        2. Resolve all set items -> track_ids -> ym_track_ids
        3. Collect tracks without ym_track_id -> skipped_track_ids
        4. Determine mode:
           a. AUTO + set.ym_playlist_id exists -> UPDATE
           b. AUTO + no ym_playlist_id -> CREATE
           c. CREATE -> always create_playlist()
           d. UPDATE + no ym_playlist_id -> raise NotFoundError
        5. CREATE path:
           a. ym_client.create_playlist(name)
           b. ym_client.add_tracks_to_playlist(kind, ym_track_ids, revision)
           c. Update set.ym_playlist_id in DB
        6. UPDATE path:
           a. Fetch existing YM playlist for current revision
           b. Clear all tracks (remove_tracks_from_playlist range 0..count)
           c. Add new tracks in set order
           d. Re-fetch for fresh revision
        7. Report progress: "Pushing track 5/20..."

        Raises:
            NotFoundError: set not found, or no latest version, or UPDATE without ym_playlist_id
            SyncTrackNotLinkedError: if ALL tracks lack ym_track_ids (partial is OK -> skipped)
            YandexMusicError: YM API failure
            SyncRevisionMismatchError: concurrent modification

        Returns:
            SetPushResult with counts and ym_playlist_kind.
        """
        ...

    async def resolve_ym_track_ids(
        self,
        track_ids: list[int],
    ) -> dict[int, str | None]:
        """Map local track_ids to yandex_track_ids via YandexMetadata table.

        Returns:
            {track_id: ym_track_id or None} for each input track.
        """
        ...
```

---

## 6. DI Chain

### Новые DI-фабрики в `app/controllers/dependencies.py`:

```python
from app.services.sync import PlaylistSyncService, SetPushService
from app.core.progress import NullProgress

async def get_ym_client() -> YandexMusicClient:
    """YM client from lifespan context."""
    ctx = get_context()
    return ctx.lifespan_context["ym_client"]

async def get_playlist_sync_service(
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
    track_repo: TrackRepository = Depends(get_track_repo),
    ym_client: YandexMusicClient = Depends(get_ym_client),
) -> PlaylistSyncService:
    """PlaylistSyncService with injected repos and YM client.

    NB: progress callback is NOT injected here -- tool layer creates
    MCPProgressAdapter from ctx and passes it post-construction:
        service = Depends(get_playlist_sync_service)
        service._progress = MCPProgressAdapter(ctx)
    Or better: service factory accepts progress as arg.
    """
    return PlaylistSyncService(
        playlist_repo=playlist_repo,
        track_repo=track_repo,
        ym_client=ym_client,
        progress=NullProgress(),  # tool layer replaces with MCPProgressAdapter
    )

async def get_set_push_service(
    set_repo: SetRepository = Depends(get_set_repo),
    track_repo: TrackRepository = Depends(get_track_repo),
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),
    ym_client: YandexMusicClient = Depends(get_ym_client),
) -> SetPushService:
    return SetPushService(
        set_repo=set_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
        ym_client=ym_client,
        progress=NullProgress(),
    )
```

### DI chain diagram:

```text
get_db_session() [cached per-request]
├── get_playlist_repo(session) ─────┐
├── get_track_repo(session) ────────┤
│                                   ├── get_playlist_sync_service(repos, ym_client)
get_ym_client() [from lifespan] ────┘

get_db_session() [same session]
├── get_set_repo(session) ──────────┐
├── get_track_repo(session) ────────┤
├── get_playlist_repo(session) ─────┤── get_set_push_service(repos, ym_client)
get_ym_client() [from lifespan] ────┘
```

### Альтернатива для progress injection

Вместо мутации `_progress` после DI, чище использовать паттерн "method accepts progress":

```python
# Вариант A (предпочтительный): progress как параметр метода
async def apply_sync(
    self,
    playlist_id: int,
    direction: SyncDirection,
    ...,
    progress: ProgressCallback | None = None,  # tool layer передаёт здесь
) -> SyncResult: ...

# Вариант B: progress в __init__ (текущий дизайн)
# Плюс: один раз настроил, все методы используют
# Минус: DI создаёт с NullProgress, tool должен заменить
```

**Рекомендация**: Вариант A -- progress как параметр `apply_sync` и `push`. DI-фабрика не знает о progress, tool передаёт адаптер при вызове. `__init__` хранит только repos и ym_client.

Тогда финальные сигнатуры `__init__`:

```python
class PlaylistSyncService:
    def __init__(
        self,
        playlist_repo: PlaylistRepository,
        track_repo: TrackRepository,
        ym_client: YandexMusicClient,
    ) -> None: ...

class SetPushService:
    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        ym_client: YandexMusicClient,
    ) -> None: ...
```

И DI-фабрики упрощаются -- не нужен NullProgress.

---

## 7. Tool Layer Integration

Как tools используют сервисы (псевдокод, не реализация):

```python
# app/controllers/tools/sync.py

@mcp.tool(tags={"sync"}, annotations={"readOnlyHint": False, "openWorldHint": True})
async def sync_playlist(
    playlist_id: int,
    direction: Literal["pull", "push", "bidirectional"] = "pull",
    conflict_strategy: Literal["source_wins", "ask", "skip"] = "source_wins",
    dry_run: bool = False,
    service: PlaylistSyncService = Depends(get_playlist_sync_service),
    ctx: Context = CurrentContext(),
) -> SyncResult:
    """Bidirectional sync between local playlist and Yandex Music."""
    progress = MCPProgressAdapter(ctx)

    # Phase 1: compute diff
    diff = await service.compute_diff(playlist_id, SyncDirection(direction))

    # Phase 2: handle conflicts via elicitation if strategy=ask
    resolutions: dict[int, str] | None = None
    if diff.conflicts and conflict_strategy == "ask":
        resolutions = {}
        for conflict in diff.conflicts:
            choice = await safe_elicit(ctx, ...)
            resolutions[conflict.track_id] = choice

    # Phase 3: apply
    return await service.apply_sync(
        playlist_id=playlist_id,
        direction=SyncDirection(direction),
        conflict_strategy=ConflictStrategy(conflict_strategy),
        conflict_resolutions=resolutions,
        dry_run=dry_run,
        progress=progress,
    )
```

---

## 8. Repository Dependencies

Сервисам нужен доступ к `YandexMetadata` для маппинга track_id <-> ym_track_id.
Два варианта:

**Вариант A**: добавить метод в `TrackRepository`:
```python
class TrackRepository:
    async def get_ym_track_ids(self, track_ids: list[int]) -> dict[int, str | None]:
        """Batch lookup: track_id -> yandex_track_id via YandexMetadata."""
        ...
```

**Вариант B**: отдельный `PlatformRepository`:
```python
class PlatformRepository:
    async def get_ym_mapping(self, track_ids: list[int]) -> dict[int, str | None]: ...
    async def get_ym_metadata_by_ym_id(self, ym_track_id: str) -> YandexMetadata | None: ...
```

**Рекомендация**: Вариант A. `PlatformRepository` избыточен на текущем этапе -- `TrackRepository` уже является точкой входа для track-ориентированных запросов. Если позже появятся Spotify/Beatport sync, тогда извлечь `PlatformRepository`.

---

## 9. Summary Table

| Компонент | Файл | Зависимости |
|-----------|------|-------------|
| `SyncError` hierarchy | `app/core/errors.py` | -- |
| `ProgressCallback` protocol | `app/core/progress.py` | -- |
| `MCPProgressAdapter` | `app/controllers/adapters.py` | `fastmcp.Context` |
| `NullProgress` | `app/core/progress.py` | -- |
| Sync data types | `app/services/sync_types.py` | `pydantic` |
| `PlaylistSyncService` | `app/services/sync.py` | `PlaylistRepo`, `TrackRepo`, `YMClient` |
| `SetPushService` | `app/services/sync.py` | `SetRepo`, `TrackRepo`, `PlaylistRepo`, `YMClient` |
| DI factories | `app/controllers/dependencies.py` | existing + `get_ym_client` |
| Tool wrappers | `app/controllers/tools/sync.py` | services via `Depends` |
