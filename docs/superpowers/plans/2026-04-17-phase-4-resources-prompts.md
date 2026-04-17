# Phase 4 — Resources + Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full resource (~26 URIs) and prompt (6 recipes) surface for `app/v2/` per blueprint §§8–9 — typed Pydantic responses, FastMCP v3 `Message`/`PromptResult`/`ResourceResult` patterns, URI-template matching, static reference blobs, and session-scoped state resources — with every file covered by a URI-matching + shape-verifying test.

**Architecture:** Resources and prompts are the LLM-facing **read** surface complementing the Phase 3 tool (write) surface. Resources dispatch through `uow` + `EntityRegistry` for live data and serve static knowledge blobs from `app/v2/domain/`. Prompts are recipes — pure text builders returning `PromptResult(messages=[Message(...)], description=...)` — that chain Phase 3 tools in a deterministic order. No business logic leaks into this layer; resources call repositories / registries, prompts contain only string templates and light parameter formatting.

**Tech Stack:** Python 3.12, FastMCP v3 (`@resource`, `@prompt`, `fastmcp.resources.ResourceResult`/`ResourceContent`, `fastmcp.prompts.Message`/`PromptResult`), Pydantic v2, pytest + pytest-asyncio, aiosqlite (tests), `fastmcp.client.Client` for in-memory test transport.

**Spec reference:** `docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md` §§8, 9, 12, 15.5.

---

## File Structure

Files created by this plan (exact paths, each self-contained):

### Source code (`app/v2/resources/`, `app/v2/prompts/`)

```bash
app/v2/resources/
├── __init__.py                    # registers all resource modules (eager-import for FileSystemProvider)
├── _shared.py                     # RESOURCE_META, ICON_*, annotation constants, json_dump helper
├── track.py                       # local://tracks/{id}, features, audit, suggest_next, suggest_replacement
├── playlist.py                    # local://playlists/{id}, audit
├── set.py                         # local://sets/{id}/{view}, cheatsheet, narrative, review, versions/compare
├── transition.py                  # local://transition/{from}/{to}/score, explain
├── transition_history.py          # local://transition_history/best_pairs, history
├── session.py                     # session://set-draft, tool-history, energy_trend
├── schema.py                      # schema://entities, schema://entities/{entity}, schema://providers, schema://providers/{name}
└── reference/
    ├── __init__.py
    ├── camelot.py                 # reference://camelot
    ├── subgenres.py               # reference://subgenres
    ├── templates.py               # reference://templates
    └── audit_rules.py             # reference://audit_rules

app/v2/prompts/
├── __init__.py                    # registers all prompts
├── _shared.py                     # PROMPT_META constant
├── dj_expert_session.py
├── build_set_workflow.py
├── deliver_set_workflow.py
├── expand_playlist_workflow.py
├── full_pipeline.py
└── quick_mix_check.py
```

### Schemas (`app/v2/schemas/resource_views.py`)

New Pydantic view models dedicated to resource output shapes (distinct from entity CRUD views):

```bash
app/v2/schemas/
└── resource_views.py              # TrackAuditView, PlaylistAuditView, SetSummaryView, SetCheatsheetView,
                                   # SetNarrativeView, SetReviewView, SetCompareView, TransitionScoreView,
                                   # TransitionExplainView, BestPairsView, TransitionHistoryView,
                                   # SessionDraftView, SessionToolHistoryView, SessionEnergyTrendView,
                                   # SchemaIndexView, SchemaEntityView, SchemaProviderIndexView,
                                   # SchemaProviderView, SuggestNextView, SuggestReplacementView
```

### Tests (`tests/v2/resources/`, `tests/v2/prompts/`)

```bash
tests/v2/resources/
├── __init__.py
├── conftest.py                   # client fixture, seeded_db with track/playlist/set/features
├── test_resource_registration.py # all expected URIs registered, tags, read-only annotation
├── test_track_resources.py
├── test_playlist_resources.py
├── test_set_resources.py
├── test_transition_resources.py
├── test_transition_history_resources.py
├── test_session_resources.py
├── test_schema_resources.py
└── test_reference_resources.py

tests/v2/prompts/
├── __init__.py
├── conftest.py
├── test_prompt_registration.py
├── test_dj_expert_session.py
├── test_build_set_workflow.py
├── test_deliver_set_workflow.py
├── test_expand_playlist_workflow.py
├── test_full_pipeline.py
└── test_quick_mix_check.py
```

### Config updates

- `.importlinter` — extend Phase 1 contracts with `resources-no-tools` and `prompts-pure` contracts (resources must not import tools; prompts must not import repositories/tools).

---

## Preconditions

Before starting Phase 4, the following MUST be in place from Phase 1–3:

- `app/v2/shared/errors.py` (`NotFoundError`, `ValidationError`)
- `app/v2/registry/entity.py` (`EntityRegistry`, `EntityConfig`)
- `app/v2/registry/provider.py` (`ProviderRegistry`, `Provider` protocol)
- `app/v2/repositories/unit_of_work.py` (`UnitOfWork` with `.tracks`, `.playlists`, `.sets`, `.set_versions`, `.track_features`, `.transitions`, `.transition_history`)
- `app/v2/server/di.py` (`get_uow`, `get_provider_registry`, `get_session_store`)
- `app/v2/domain/camelot/wheel.py` (`CAMELOT_WHEEL`, `camelot_distance`)
- `app/v2/domain/template/registry.py` (`SET_TEMPLATES`, `SetTemplateDefinition`)
- `app/v2/domain/audit/rules.py` (`TECHNO_AUDIT_SPEC`, `audit_track`)
- `app/v2/domain/transition/scorer.py` (`TransitionScorer`)
- `app/v2/schemas/track.py` (`TrackView`)
- `app/v2/tools/` — Phase 3 entity/provider/compute tools registered

If any precondition is missing, STOP and escalate; do not stub.

---

## Task 1: Create resource + prompt package skeleton

**Files:**
- Create: `app/v2/resources/__init__.py`
- Create: `app/v2/resources/reference/__init__.py`
- Create: `app/v2/prompts/__init__.py`
- Create: `tests/v2/resources/__init__.py`
- Create: `tests/v2/prompts/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p app/v2/resources/reference app/v2/prompts
mkdir -p tests/v2/resources tests/v2/prompts
```

- [ ] **Step 2: Write `app/v2/resources/__init__.py`**

```python
"""FastMCP resources for v2.

FileSystemProvider auto-discovers `@resource` decorators in submodules.
This package keeps the following guarantees:

1. All resource functions return ``str | bytes | ResourceResult`` (never dict/list).
2. JSON payloads are serialized with ``json.dumps`` and ``mime_type="application/json"``.
3. Every resource carries ``tags={...}`` + read-only annotations.
4. Tests in ``tests/v2/resources/`` verify URI template matching and payload shape.
"""
```

- [ ] **Step 3: Write `app/v2/resources/reference/__init__.py`**

```python
"""Static reference blobs — Camelot wheel, subgenres, templates, audit rules.

Reference resources serve large static JSON payloads assembled at import time
from ``app.v2.domain.*``. They never touch the database.
"""
```

- [ ] **Step 4: Write `app/v2/prompts/__init__.py`**

```python
"""FastMCP workflow prompts for v2.

All prompts return ``fastmcp.prompts.PromptResult`` — the v3 type.
Prompts must NOT import repositories, tools, or providers directly — they
are pure text builders chaining the Phase 3 tool surface.
"""
```

- [ ] **Step 5: Write empty `__init__.py` for test packages**

```python
# tests/v2/resources/__init__.py and tests/v2/prompts/__init__.py
""""""
```

- [ ] **Step 6: Verify importability**

```bash
uv run python -c "import app.v2.resources; import app.v2.resources.reference; import app.v2.prompts"
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add app/v2/resources app/v2/prompts tests/v2/resources tests/v2/prompts
git commit -m "feat(v2): create resources and prompts package skeleton

Empty packages per blueprint phase 4. FileSystemProvider will
auto-discover @resource and @prompt decorators once modules are filled."
```

---

## Task 2: `app/v2/resources/_shared.py` — resource metadata constants

**Files:**
- Create: `app/v2/resources/_shared.py`
- Test: `tests/v2/resources/test_resource_registration.py` (partial — shared constants)

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_resource_registration.py
"""Resource metadata constants + registration tests."""

from __future__ import annotations

from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

def test_annotations_read_only_is_dict() -> None:
    assert isinstance(ANNOTATIONS_READ_ONLY, dict)
    assert ANNOTATIONS_READ_ONLY["readOnlyHint"] is True
    assert ANNOTATIONS_READ_ONLY["idempotentHint"] is True

def test_resource_meta_has_version() -> None:
    assert "version" in RESOURCE_META
    assert isinstance(RESOURCE_META["version"], str)

def test_json_dump_returns_string() -> None:
    out = json_dump({"a": 1, "b": [2, 3]})
    assert isinstance(out, str)
    assert '"a":1' in out.replace(" ", "")

def test_json_dump_handles_nested() -> None:
    out = json_dump({"nested": {"list": [1, 2, {"k": "v"}]}})
    assert "nested" in out and "list" in out and "v" in out

def test_json_dump_preserves_unicode() -> None:
    out = json_dump({"name": "Детройт"})
    # We explicitly set ensure_ascii=False to keep non-ASCII readable.
    assert "Детройт" in out
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/resources/test_resource_registration.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.v2.resources._shared'`.

- [ ] **Step 3: Write `app/v2/resources/_shared.py`**

```python
"""Shared resource constants.

All resources share these annotations and meta so the MCP client sees a
uniform surface. Using constants prevents drift between files.
"""

from __future__ import annotations

import json
from typing import Any

from app.v2 import __version__

ANNOTATIONS_READ_ONLY: dict[str, bool] = {
    "readOnlyHint": True,
    "idempotentHint": True,
}
"""Standard read-only annotation set.

Resources are by definition read-only (MCP spec). The hints repeat this so
clients that rely on annotations without checking the resource kind still
make the right decision.
"""

RESOURCE_META: dict[str, str] = {
    "version": __version__,
    "layer": "resource",
}
"""Static meta attached to every resource for observability."""

def json_dump(payload: Any) -> str:
    """Serialize a payload to JSON with stable settings.

    - ``ensure_ascii=False``  — keep non-ASCII (subgenre names in Russian, etc.)
    - ``separators=(",",":")`` — compact output, no whitespace padding
    - ``sort_keys=False`` — preserve caller-defined ordering (field presets matter)
    """
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_resource_registration.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/_shared.py tests/v2/resources/test_resource_registration.py
git commit -m "feat(v2): resource metadata constants and json_dump helper

ANNOTATIONS_READ_ONLY, RESOURCE_META, json_dump — shared by all resource
modules. ensure_ascii=False preserves Cyrillic subgenre names."
```

---

## Task 3: `app/v2/prompts/_shared.py` — prompt metadata constants

**Files:**
- Create: `app/v2/prompts/_shared.py`
- Test: inline in `tests/v2/prompts/test_prompt_registration.py` (partial)

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_prompt_registration.py
"""Prompt metadata constants + registration tests."""

from __future__ import annotations

from app.v2.prompts._shared import PROMPT_META

def test_prompt_meta_has_version() -> None:
    assert "version" in PROMPT_META
    assert "layer" in PROMPT_META
    assert PROMPT_META["layer"] == "prompt"
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/prompts/test_prompt_registration.py::test_prompt_meta_has_version -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/prompts/_shared.py`**

```python
"""Shared prompt constants."""

from __future__ import annotations

from app.v2 import __version__

PROMPT_META: dict[str, str] = {
    "version": __version__,
    "layer": "prompt",
}
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_prompt_registration.py::test_prompt_meta_has_version -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/prompts/_shared.py tests/v2/prompts/test_prompt_registration.py
git commit -m "feat(v2): prompt metadata constants

PROMPT_META shared across workflow prompts for observability."
```

---

## Task 4: `app/v2/schemas/resource_views.py` — Pydantic view models for resources

**Files:**
- Create: `app/v2/schemas/resource_views.py`
- Test: `tests/v2/schemas/test_resource_views.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/schemas/test_resource_views.py
"""Resource view schemas — validate field shape and serialization."""

from __future__ import annotations

import json

import pytest

from app.v2.schemas.resource_views import (
    BestPairsView,
    PlaylistAuditView,
    SchemaEntityView,
    SchemaIndexView,
    SchemaProviderIndexView,
    SchemaProviderView,
    SessionDraftView,
    SessionEnergyTrendView,
    SessionToolHistoryView,
    SetCheatsheetView,
    SetCompareView,
    SetNarrativeView,
    SetReviewView,
    SetSummaryView,
    SetTracksView,
    SetTransitionsView,
    SuggestNextView,
    SuggestReplacementView,
    TrackAuditView,
    TransitionExplainView,
    TransitionHistoryView,
    TransitionScoreView,
)

def test_track_audit_view_validates() -> None:
    view = TrackAuditView(
        track_id=1, passed=True, violations=[], score=0.95, criteria_checked=14
    )
    assert view.track_id == 1
    assert view.passed is True
    dumped = json.loads(view.model_dump_json())
    assert dumped["passed"] is True
    assert dumped["violations"] == []

def test_playlist_audit_view_accepts_items() -> None:
    view = PlaylistAuditView(
        playlist_id=42,
        total_tracks=10,
        passed=8,
        failed=2,
        per_track=[
            {"track_id": 1, "passed": True, "violations": []},
            {"track_id": 2, "passed": False, "violations": ["bpm < 120"]},
        ],
    )
    assert view.total_tracks == 10
    assert view.failed == 2

def test_set_summary_view_fields() -> None:
    view = SetSummaryView(
        set_id=1,
        name="Friday Night",
        template_name="classic_60",
        version_count=3,
        latest_version_id=55,
        latest_quality_score=0.82,
    )
    assert view.latest_quality_score == 0.82

def test_set_cheatsheet_view_has_lines() -> None:
    view = SetCheatsheetView(
        set_id=1,
        version_id=55,
        lines=[
            {"position": 1, "title": "A", "bpm": 124.0, "key": "8A", "energy": -8.2},
            {"position": 2, "title": "B", "bpm": 125.5, "key": "9A", "energy": -7.9},
        ],
    )
    assert len(view.lines) == 2

def test_transition_score_view_components() -> None:
    view = TransitionScoreView(
        from_track_id=1,
        to_track_id=2,
        overall=0.74,
        hard_reject=False,
        reject_reason=None,
        components={
            "bpm": 0.85, "harmonic": 0.6, "energy": 0.8,
            "spectral": 0.7, "groove": 0.72, "timbral": 0.65,
        },
    )
    assert view.components["bpm"] == 0.85

def test_transition_score_view_hard_reject() -> None:
    view = TransitionScoreView(
        from_track_id=1,
        to_track_id=2,
        overall=0.0,
        hard_reject=True,
        reject_reason="BPM difference 12.0 > 10",
        components={},
    )
    assert view.hard_reject is True
    assert "12.0" in (view.reject_reason or "")

def test_best_pairs_view_is_list() -> None:
    view = BestPairsView(
        pairs=[
            {"from_track_id": 1, "to_track_id": 2, "plays": 5, "avg_reaction": 4.2},
        ],
        limit=10,
    )
    assert view.limit == 10
    assert view.pairs[0]["plays"] == 5

def test_session_draft_view_empty() -> None:
    view = SessionDraftView(
        session_id="abc",
        tracks=[],
        target_duration_ms=None,
        template_name=None,
        last_mutation_at=None,
    )
    assert view.tracks == []

def test_schema_index_view_lists_entities() -> None:
    view = SchemaIndexView(entities=["track", "playlist", "set"])
    assert "track" in view.entities

def test_schema_entity_view_snapshot() -> None:
    view = SchemaEntityView(
        name="track",
        operations=["list", "get", "create", "update", "delete", "aggregate"],
        presets={"id": ["id"], "summary": ["id", "title", "bpm"]},
        default_preset="id",
        searchable_fields=["title"],
        filterable_fields={"bpm": ["eq", "gte", "lte", "range"]},
        sortable_fields=["bpm", "id", "title"],
        relations=["artists", "features"],
        view_schema={"type": "object"},
        filter_schema={"type": "object"},
        create_schema={"type": "object"},
        update_schema={"type": "object"},
    )
    assert view.name == "track"

def test_suggest_next_view_shape() -> None:
    view = SuggestNextView(
        from_track_id=1,
        limit=5,
        energy_direction="up",
        candidates=[
            {"track_id": 2, "title": "Drop", "score": 0.88, "bpm": 126, "key": "9A"},
        ],
    )
    assert view.energy_direction == "up"

def test_suggest_replacement_view_shape() -> None:
    view = SuggestReplacementView(
        set_id=5, position=3,
        removed_track_id=42,
        candidates=[{"track_id": 77, "score": 0.81, "reason": "similar energy + 1 bpm"}],
    )
    assert view.position == 3

def test_session_tool_history_view_shape() -> None:
    view = SessionToolHistoryView(
        session_id="abc",
        entries=[{"tool": "entity_list", "at": "2026-04-17T10:00:00Z", "ok": True}],
    )
    assert view.entries[0]["tool"] == "entity_list"

def test_session_energy_trend_view_shape() -> None:
    view = SessionEnergyTrendView(
        last_n=5,
        samples=[-10.2, -9.8, -9.0, -8.5, -8.0],
    )
    assert len(view.samples) == 5

def test_set_narrative_view_shape() -> None:
    view = SetNarrativeView(
        set_id=1,
        version_id=55,
        narrative="Opens cool, climbs through hypnotic peak, lands soft.",
        phases=[{"label": "warm_up", "start": 0, "end": 3}],
    )
    assert "Opens" in view.narrative

def test_set_review_view_shape() -> None:
    view = SetReviewView(
        set_id=1, version_id=55,
        quality_score=0.71,
        weak_transitions=[{"position": 4, "score": 0.3, "reason": "energy gap"}],
        hard_conflicts=[],
    )
    assert view.weak_transitions[0]["position"] == 4

def test_set_compare_view_shape() -> None:
    view = SetCompareView(
        set_id=1,
        version_a={"id": 10, "quality_score": 0.65},
        version_b={"id": 11, "quality_score": 0.78},
        delta=0.13,
        changed_positions=[2, 5, 7],
    )
    assert view.delta == 0.13

def test_transition_explain_view_shape() -> None:
    view = TransitionExplainView(
        from_track_id=1, to_track_id=2,
        overall=0.74,
        narrative="Smooth Camelot step, mild energy lift.",
        suggestions=["Use 32-bar bass-swap"],
    )
    assert "Camelot" in view.narrative

def test_transition_history_view_shape() -> None:
    view = TransitionHistoryView(
        limit=20,
        entries=[{"id": 1, "from_track_id": 1, "to_track_id": 2, "at": "2026-04-17T10:00:00Z", "reaction": "hot"}],
    )
    assert view.limit == 20

def test_set_tracks_view_shape() -> None:
    view = SetTracksView(
        set_id=1, version_id=55,
        tracks=[{"position": 1, "track_id": 10, "title": "A"}],
    )
    assert view.tracks[0]["position"] == 1

def test_set_transitions_view_shape() -> None:
    view = SetTransitionsView(
        set_id=1, version_id=55,
        transitions=[{"position": 1, "from_track_id": 10, "to_track_id": 11, "overall": 0.8}],
    )
    assert view.transitions[0]["overall"] == 0.8

def test_schema_provider_index_view() -> None:
    view = SchemaProviderIndexView(providers=["yandex"])
    assert "yandex" in view.providers

def test_schema_provider_view() -> None:
    view = SchemaProviderView(
        name="yandex",
        entities_supported=["track", "album", "artist", "playlist", "likes"],
        operations={"read": True, "write": True, "search": True, "download_audio": True},
    )
    assert view.operations["download_audio"] is True
```

- [ ] **Step 2: Run tests — expected FAIL (module missing)**

```bash
uv run pytest tests/v2/schemas/test_resource_views.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/schemas/resource_views.py`**

```python
"""Pydantic view models for resource payloads.

These sit alongside entity CRUD views (TrackView, PlaylistView, ...).
They describe the *shape* of resource responses — purely presentation
DTOs, never persisted. All fields are chosen to match the JSON the LLM
receives: no hidden SQLAlchemy attributes, no ORM leakage.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

# ── Track resources ─────────────────────────────────────────────

class TrackAuditView(_Base):
    track_id: int
    passed: bool
    violations: list[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=1.0)
    criteria_checked: int

class SuggestNextView(_Base):
    from_track_id: int
    limit: int
    energy_direction: str | None
    candidates: list[dict[str, Any]]

class SuggestReplacementView(_Base):
    set_id: int
    position: int
    removed_track_id: int | None
    candidates: list[dict[str, Any]]

# ── Playlist resources ──────────────────────────────────────────

class PlaylistAuditView(_Base):
    playlist_id: int
    total_tracks: int
    passed: int
    failed: int
    per_track: list[dict[str, Any]]

# ── Set resources ───────────────────────────────────────────────

class SetSummaryView(_Base):
    set_id: int
    name: str
    template_name: str | None
    version_count: int
    latest_version_id: int | None
    latest_quality_score: float | None

class SetTracksView(_Base):
    set_id: int
    version_id: int
    tracks: list[dict[str, Any]]

class SetTransitionsView(_Base):
    set_id: int
    version_id: int
    transitions: list[dict[str, Any]]

class SetCheatsheetView(_Base):
    set_id: int
    version_id: int
    lines: list[dict[str, Any]]

class SetNarrativeView(_Base):
    set_id: int
    version_id: int
    narrative: str
    phases: list[dict[str, Any]]

class SetReviewView(_Base):
    set_id: int
    version_id: int
    quality_score: float
    weak_transitions: list[dict[str, Any]]
    hard_conflicts: list[dict[str, Any]]

class SetCompareView(_Base):
    set_id: int
    version_a: dict[str, Any]
    version_b: dict[str, Any]
    delta: float
    changed_positions: list[int]

# ── Transition resources ────────────────────────────────────────

class TransitionScoreView(_Base):
    from_track_id: int
    to_track_id: int
    overall: float
    hard_reject: bool
    reject_reason: str | None
    components: dict[str, float]

class TransitionExplainView(_Base):
    from_track_id: int
    to_track_id: int
    overall: float
    narrative: str
    suggestions: list[str]

# ── Transition history ──────────────────────────────────────────

class BestPairsView(_Base):
    limit: int
    pairs: list[dict[str, Any]]

class TransitionHistoryView(_Base):
    limit: int
    entries: list[dict[str, Any]]

# ── Session resources ───────────────────────────────────────────

class SessionDraftView(_Base):
    session_id: str
    tracks: list[dict[str, Any]]
    target_duration_ms: int | None
    template_name: str | None
    last_mutation_at: str | None

class SessionToolHistoryView(_Base):
    session_id: str
    entries: list[dict[str, Any]]

class SessionEnergyTrendView(_Base):
    last_n: int
    samples: list[float]

# ── Schema introspection ────────────────────────────────────────

class SchemaIndexView(_Base):
    entities: list[str]

class SchemaEntityView(_Base):
    name: str
    operations: list[str]
    presets: dict[str, list[str]]
    default_preset: str
    searchable_fields: list[str]
    filterable_fields: dict[str, list[str]]
    sortable_fields: list[str]
    relations: list[str]
    view_schema: dict[str, Any]
    filter_schema: dict[str, Any]
    create_schema: dict[str, Any]
    update_schema: dict[str, Any]

class SchemaProviderIndexView(_Base):
    providers: list[str]

class SchemaProviderView(_Base):
    name: str
    entities_supported: list[str]
    operations: dict[str, bool]
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/schemas/test_resource_views.py -v
```
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/schemas/resource_views.py tests/v2/schemas/test_resource_views.py
git commit -m "feat(v2): resource view schemas (Pydantic)

23 view models for track audit, set summary/cheatsheet/review,
transition score/explain, session draft, schema introspection.
Frozen + extra='forbid' — strict presentation DTOs."
```

---

## Task 5: `tests/v2/resources/conftest.py` — shared test fixtures

**Files:**
- Create: `tests/v2/resources/conftest.py`

- [ ] **Step 1: Write `tests/v2/resources/conftest.py`**

```python
"""Shared fixtures for resource tests.

Provides:
- ``mcp_app`` — a FastMCP server with all resources registered.
- ``client`` — in-memory FastMCP Client bound to ``mcp_app``.
- ``seeded_db`` — UoW with seed tracks + playlist + set + features.
- ``session_store`` — in-memory session state (set draft, tool history, energy samples).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastmcp import FastMCP
from fastmcp.client import Client
from sqlalchemy.ext.asyncio import AsyncSession

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.server.session_store import InMemorySessionStore

@pytest_asyncio.fixture
async def mcp_app() -> AsyncIterator[FastMCP]:
    """Minimal MCP app with all Phase 4 resources registered.

    We import the resource modules so @resource decorators run — the
    FileSystemProvider mechanism is exercised indirectly via Client.
    """
    from app.v2.server.app import build_mcp_app_for_tests

    app = await build_mcp_app_for_tests()
    yield app

@pytest_asyncio.fixture
async def client(mcp_app: FastMCP) -> AsyncIterator[Client]:
    async with Client(mcp_app) as c:
        yield c

@pytest_asyncio.fixture
async def seeded_db(seeded_session: AsyncSession) -> AsyncIterator[UnitOfWork]:
    """UoW with a canonical seed: 3 tracks, 1 playlist, 1 set+version+items, features."""
    from tests.v2.resources._seed import seed_canonical_state

    uow = UnitOfWork(seeded_session)
    async with uow:
        await seed_canonical_state(uow)
        yield uow

@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()
```

- [ ] **Step 2: Write `tests/v2/resources/_seed.py`** (helper used by fixture)

```python
"""Canonical seed used across resource tests."""

from __future__ import annotations

from app.v2.repositories.unit_of_work import UnitOfWork

async def seed_canonical_state(uow: UnitOfWork) -> None:
    """Insert the seed graph used by every resource test.

    3 tracks (ids 1, 2, 3) each with features (bpm 124, 126, 128, key_code 5, 8, 9),
    1 playlist (id 10) referencing them, 1 set (id 100) with one version (id 1000)
    holding the 3 tracks in order, 2 transitions persisted between them.

    IMPLEMENTATION: call uow.tracks.create(...), uow.track_features.create(...),
    uow.playlists.create(...), uow.sets.create(...), uow.set_versions.create(...),
    uow.transitions.create(...). Repositories are already available from Phase 2.
    """
    # Tracks
    await uow.tracks.create(id=1, title="Alpha", duration_ms=360_000, status=0)
    await uow.tracks.create(id=2, title="Beta", duration_ms=380_000, status=0)
    await uow.tracks.create(id=3, title="Gamma", duration_ms=400_000, status=0)
    # Features (minimal — only fields the resource asserts on)
    await uow.track_features.create(
        track_id=1, bpm=124.0, key_code=5, integrated_lufs=-10.2,
        energy_mean=0.42, kick_prominence=0.30, onset_rate=5.1,
        spectral_centroid_hz=1800.0, analysis_level=3, mood="hypnotic",
    )
    await uow.track_features.create(
        track_id=2, bpm=126.0, key_code=8, integrated_lufs=-9.0,
        energy_mean=0.55, kick_prominence=0.42, onset_rate=6.0,
        spectral_centroid_hz=2100.0, analysis_level=3, mood="peak_time",
    )
    await uow.track_features.create(
        track_id=3, bpm=128.0, key_code=9, integrated_lufs=-8.0,
        energy_mean=0.68, kick_prominence=0.55, onset_rate=7.0,
        spectral_centroid_hz=2500.0, analysis_level=3, mood="driving",
    )
    # Playlist + items
    pl = await uow.playlists.create(id=10, name="Test PL", source_of_truth="local")
    await uow.playlists.add_items(pl.id, track_ids=[1, 2, 3])
    # Set + version + items
    s = await uow.sets.create(id=100, name="Test Set", template_name="classic_60")
    v = await uow.set_versions.create(id=1000, set_id=s.id, label="v1", quality_score=0.78)
    await uow.set_versions.add_items(v.id, track_ids=[1, 2, 3])
    # Transitions (1→2, 2→3)
    await uow.transitions.create(
        from_track_id=1, to_track_id=2, bpm_score=0.9, harmonic_score=0.5,
        energy_score=0.8, spectral_score=0.7, groove_score=0.7, timbral_score=0.6,
        overall_quality=0.74, hard_reject=False,
    )
    await uow.transitions.create(
        from_track_id=2, to_track_id=3, bpm_score=0.88, harmonic_score=0.9,
        energy_score=0.82, spectral_score=0.72, groove_score=0.75, timbral_score=0.65,
        overall_quality=0.81, hard_reject=False,
    )
    await uow.session.commit()
```

- [ ] **Step 3: Smoke-check imports**

```bash
uv run python -c "import tests.v2.resources.conftest; import tests.v2.resources._seed"
```
Expected: clean (or `ModuleNotFoundError` only for `app.v2.server.app.build_mcp_app_for_tests` / `InMemorySessionStore` — filled in later tasks; this is OK if conftest is not yet imported by a test).

- [ ] **Step 4: Commit**

```bash
git add tests/v2/resources/conftest.py tests/v2/resources/_seed.py
git commit -m "test(v2): shared resource fixtures and canonical seed

client + seeded_db + session_store. Seed: 3 tracks, features L3,
1 playlist, 1 set with 3-track version, 2 transitions."
```

---

## Task 6: `app/v2/server/session_store.py` — in-memory session state

**Files:**
- Create: `app/v2/server/session_store.py`
- Test: `tests/v2/server/test_session_store.py`

This is a prerequisite for `session://*` resources. It is intentionally tiny and lives at the server layer.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/server/test_session_store.py
"""InMemorySessionStore tests."""

from __future__ import annotations

from app.v2.server.session_store import InMemorySessionStore

def test_get_empty_draft() -> None:
    store = InMemorySessionStore()
    draft = store.get_draft("s1")
    assert draft["tracks"] == []
    assert draft["template_name"] is None

def test_update_draft_then_get() -> None:
    store = InMemorySessionStore()
    store.update_draft("s1", tracks=[1, 2, 3], template_name="classic_60")
    draft = store.get_draft("s1")
    assert draft["tracks"] == [1, 2, 3]
    assert draft["template_name"] == "classic_60"

def test_sessions_are_isolated() -> None:
    store = InMemorySessionStore()
    store.update_draft("s1", tracks=[1])
    store.update_draft("s2", tracks=[9])
    assert store.get_draft("s1")["tracks"] == [1]
    assert store.get_draft("s2")["tracks"] == [9]

def test_tool_history_append_and_read() -> None:
    store = InMemorySessionStore()
    store.append_tool("s1", tool="entity_list", ok=True)
    store.append_tool("s1", tool="entity_get", ok=False)
    entries = store.get_tool_history("s1")
    assert len(entries) == 2
    assert entries[0]["tool"] == "entity_list"

def test_energy_sample_fifo() -> None:
    store = InMemorySessionStore(energy_capacity=3)
    for v in (-10.0, -9.5, -9.0, -8.5):
        store.append_energy("s1", v)
    samples = store.get_energy_samples("s1", last_n=5)
    # Capacity=3 drops the oldest
    assert samples == [-9.5, -9.0, -8.5]

def test_energy_last_n_slice() -> None:
    store = InMemorySessionStore(energy_capacity=100)
    for v in (-10.0, -9.0, -8.0, -7.0):
        store.append_energy("s1", v)
    assert store.get_energy_samples("s1", last_n=2) == [-8.0, -7.0]
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/server/test_session_store.py -v
```
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/server/session_store.py`**

```python
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
from collections.abc import Mapping
from datetime import datetime
from threading import Lock
from typing import Any

from app.v2.shared.time import utc_timestamp_iso

class InMemorySessionStore:
    """Single-process session state. Swap for Redis in Phase 5 if needed."""

    def __init__(self, *, energy_capacity: int = 50, tool_history_capacity: int = 100) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}
        self._tool_history: dict[str, deque[dict[str, Any]]] = {}
        self._energy: dict[str, deque[float]] = {}
        self._energy_cap = energy_capacity
        self._history_cap = tool_history_capacity
        self._lock = Lock()

    # ── Draft ────────────────────────────────────────────────────

    def get_draft(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            d = self._drafts.get(session_id)
            if d is None:
                return {
                    "session_id": session_id,
                    "tracks": [],
                    "target_duration_ms": None,
                    "template_name": None,
                    "last_mutation_at": None,
                }
            return dict(d)

    def update_draft(self, session_id: str, **fields: Any) -> None:
        with self._lock:
            d = self._drafts.setdefault(
                session_id,
                {
                    "session_id": session_id,
                    "tracks": [],
                    "target_duration_ms": None,
                    "template_name": None,
                    "last_mutation_at": None,
                },
            )
            d.update(fields)
            d["last_mutation_at"] = utc_timestamp_iso()

    # ── Tool history ─────────────────────────────────────────────

    def append_tool(self, session_id: str, *, tool: str, ok: bool, **extra: Any) -> None:
        with self._lock:
            q = self._tool_history.setdefault(session_id, deque(maxlen=self._history_cap))
            entry: dict[str, Any] = {"tool": tool, "ok": ok, "at": utc_timestamp_iso()}
            entry.update(extra)
            q.append(entry)

    def get_tool_history(self, session_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
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
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/server/test_session_store.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/server/session_store.py tests/v2/server/test_session_store.py
git commit -m "feat(v2): in-memory session store for session:// resources

Holds draft + tool history + energy ring buffer per session_id.
Thread-safe via Lock. Swappable for Redis later."
```

---

## Task 7: `app/v2/resources/track.py` — track-scoped resources

**Files:**
- Create: `app/v2/resources/track.py`
- Test: `tests/v2/resources/test_track_resources.py`

Resources to implement:

1. `local://tracks/{id}` — single track view
2. `local://tracks/{id}/features` — audio features
3. `local://tracks/{id}/audit` — techno audit
4. `local://tracks/{id}/suggest_next{?limit,energy_direction}` — next-track candidates
5. `local://tracks/{id}/suggest_replacement/{set_id}/{position}` — replacement suggestions

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_track_resources.py
"""Track resource tests — URI template matching + JSON payload shape."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_read_track_by_id(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1")
    assert len(result) == 1
    payload = json.loads(result[0].text)
    assert payload["id"] == 1
    assert payload["title"] == "Alpha"
    assert result[0].mimeType == "application/json"

async def test_read_track_features(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/features")
    payload = json.loads(result[0].text)
    assert payload["track_id"] == 1
    assert payload["bpm"] == 124.0
    assert payload["mood"] == "hypnotic"

async def test_read_track_audit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/audit")
    payload = json.loads(result[0].text)
    assert payload["track_id"] == 1
    assert "passed" in payload
    assert "violations" in payload
    assert "criteria_checked" in payload

async def test_read_track_audit_raises_for_missing(client: Client) -> None:
    with pytest.raises(Exception):  # FastMCP wraps NotFoundError in McpError
        await client.read_resource("local://tracks/99999/audit")

async def test_suggest_next_default_limit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://tracks/1/suggest_next")
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["limit"] == 10  # default
    assert "candidates" in payload

async def test_suggest_next_with_query_params(client: Client, seeded_db: object) -> None:
    result = await client.read_resource(
        "local://tracks/1/suggest_next?limit=3&energy_direction=up"
    )
    payload = json.loads(result[0].text)
    assert payload["limit"] == 3
    assert payload["energy_direction"] == "up"

async def test_suggest_replacement(client: Client, seeded_db: object) -> None:
    result = await client.read_resource(
        "local://tracks/2/suggest_replacement/100/2"
    )
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["position"] == 2
```

- [ ] **Step 2: Run tests — expected FAIL (resources not registered)**

```bash
uv run pytest tests/v2/resources/test_track_resources.py -v
```
Expected: `ResourceNotFound` or `ModuleNotFoundError`.

- [ ] **Step 3: Write `app/v2/resources/track.py`**

```python
"""Track-scoped resources."""

from __future__ import annotations

from typing import Annotated

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.domain.audit.rules import audit_track
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.v2.schemas.resource_views import (
    SuggestNextView,
    SuggestReplacementView,
    TrackAuditView,
)
from app.v2.schemas.track import TrackView
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError

@resource(
    "local://tracks/{id}",
    mime_type="application/json",
    tags={"namespace:library", "entity:track", "view:track"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_view(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Single-track view (core fields + relations projection)."""
    row = await uow.tracks.get(id)
    if row is None:
        raise NotFoundError("track", id)
    return TrackView.model_validate(row).model_dump_json()

@resource(
    "local://tracks/{id}/features",
    mime_type="application/json",
    tags={"namespace:library", "entity:track_features", "view:features"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_features(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Audio features for a track (bpm, key, loudness, energy, spectral, rhythm)."""
    feat = await uow.track_features.get_by_track_id(id)
    if feat is None:
        raise NotFoundError("track_features", id)
    return json_dump(_track_features_payload(id, feat))

@resource(
    "local://tracks/{id}/audit",
    mime_type="application/json",
    tags={"namespace:library", "entity:track", "view:audit"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_audit(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Run the techno audit rules against a single track."""
    feat = await uow.track_features.get_by_track_id(id)
    if feat is None:
        raise NotFoundError("track_features", id)
    report = audit_track(feat)
    view = TrackAuditView(
        track_id=id,
        passed=report.passed,
        violations=list(report.violations),
        score=report.score,
        criteria_checked=report.criteria_checked,
    )
    return view.model_dump_json()

@resource(
    "local://tracks/{id}/suggest_next{?limit,energy_direction}",
    mime_type="application/json",
    tags={"namespace:reasoning", "view:suggest_next"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_suggest_next(
    id: int,
    limit: int = 10,
    energy_direction: str | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Suggest ``limit`` next-track candidates for a free-standing track.

    ``energy_direction`` ∈ {``up``, ``down``, ``flat``, ``None``}.
    """
    if await uow.tracks.get(id) is None:
        raise NotFoundError("track", id)
    candidates = await _compute_suggest_next(uow, track_id=id, limit=limit, direction=energy_direction)
    view = SuggestNextView(
        from_track_id=id,
        limit=limit,
        energy_direction=energy_direction,
        candidates=candidates,
    )
    return view.model_dump_json()

@resource(
    "local://tracks/{id}/suggest_replacement/{set_id}/{position}",
    mime_type="application/json",
    tags={"namespace:reasoning", "view:suggest_replacement"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def track_suggest_replacement(
    id: int,
    set_id: int,
    position: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Suggest replacements for ``track_id=id`` at ``position`` in ``set_id``."""
    if await uow.sets.get(set_id) is None:
        raise NotFoundError("set", set_id)
    candidates = await _compute_suggest_replacement(
        uow, set_id=set_id, position=position, removed_track_id=id
    )
    view = SuggestReplacementView(
        set_id=set_id,
        position=position,
        removed_track_id=id,
        candidates=candidates,
    )
    return view.model_dump_json()

# ── internal helpers (no side effects, no I/O beyond `uow`) ────

def _track_features_payload(track_id: int, feat: object) -> dict:
    """Project the subset of features we publish on this endpoint.

    Kept small and explicit; do NOT dump the ORM row directly — that would
    leak SQLAlchemy state.
    """
    return {
        "track_id": track_id,
        "bpm": getattr(feat, "bpm", None),
        "bpm_confidence": getattr(feat, "bpm_confidence", None),
        "key_code": getattr(feat, "key_code", None),
        "integrated_lufs": getattr(feat, "integrated_lufs", None),
        "energy_mean": getattr(feat, "energy_mean", None),
        "kick_prominence": getattr(feat, "kick_prominence", None),
        "onset_rate": getattr(feat, "onset_rate", None),
        "spectral_centroid_hz": getattr(feat, "spectral_centroid_hz", None),
        "analysis_level": getattr(feat, "analysis_level", None),
        "mood": getattr(feat, "mood", None),
        "mood_confidence": getattr(feat, "mood_confidence", None),
    }

async def _compute_suggest_next(
    uow: UnitOfWork, *, track_id: int, limit: int, direction: str | None,
) -> list[dict]:
    """Compute next-track candidates using the in-DB transition+features data.

    Strategy: pull the top N transitions originating from ``track_id`` sorted by
    ``overall_quality``; filter by energy direction using features; project.
    """
    rows = await uow.transitions.list_from(track_id, limit=limit * 3)
    out: list[dict] = []
    for r in rows:
        feat_to = await uow.track_features.get_by_track_id(r.to_track_id)
        if feat_to is None:
            continue
        if direction == "up" and (feat_to.energy_mean or 0) <= 0:
            continue
        if direction == "down" and (feat_to.energy_mean or 0) >= 1:
            continue
        track = await uow.tracks.get(r.to_track_id)
        out.append({
            "track_id": r.to_track_id,
            "title": track.title if track else "",
            "score": r.overall_quality,
            "bpm": feat_to.bpm,
            "key": feat_to.key_code,
        })
        if len(out) >= limit:
            break
    return out

async def _compute_suggest_replacement(
    uow: UnitOfWork, *, set_id: int, position: int, removed_track_id: int,
) -> list[dict]:
    """Candidate replacements: tracks with similar BPM/energy to removed_track_id,
    excluding tracks already in the set's latest version."""
    ver = await uow.set_versions.get_latest(set_id)
    if ver is None:
        return []
    items = await uow.set_versions.get_items(ver.id)
    excluded = {it.track_id for it in items}
    target_feat = await uow.track_features.get_by_track_id(removed_track_id)
    if target_feat is None:
        return []
    bpm = target_feat.bpm or 0.0
    candidates = await uow.tracks.search_by_bpm_range(
        bpm_min=bpm - 2.0, bpm_max=bpm + 2.0, exclude_ids=excluded, limit=10,
    )
    out: list[dict] = []
    for t in candidates:
        out.append({
            "track_id": t.id,
            "title": t.title,
            "score": 0.0,  # placeholder — callers can re-score with score_pool
            "reason": f"bpm within 2 of {bpm}",
        })
    return out
```

- [ ] **Step 4: Run tests — expected PASS (after resources load through FileSystemProvider)**

```bash
uv run pytest tests/v2/resources/test_track_resources.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/track.py tests/v2/resources/test_track_resources.py
git commit -m "feat(v2): track-scoped resources (5 URIs)

local://tracks/{id}, .../features, .../audit, .../suggest_next{?limit,...},
.../suggest_replacement/{set_id}/{position}. All JSON, Pydantic-typed."
```

---

## Task 8: `app/v2/resources/playlist.py` — playlist resources

**Files:**
- Create: `app/v2/resources/playlist.py`
- Test: `tests/v2/resources/test_playlist_resources.py`

Resources:
1. `local://playlists/{id}{?include_tracks}` — playlist view, optional track expansion
2. `local://playlists/{id}/audit` — audit all tracks in the playlist

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_playlist_resources.py
"""Playlist resource tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_read_playlist_summary(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://playlists/10")
    payload = json.loads(result[0].text)
    assert payload["id"] == 10
    assert payload["name"] == "Test PL"
    assert "tracks" not in payload

async def test_read_playlist_with_tracks(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://playlists/10?include_tracks=true")
    payload = json.loads(result[0].text)
    assert payload["id"] == 10
    assert isinstance(payload.get("tracks"), list)
    assert len(payload["tracks"]) == 3
    assert payload["tracks"][0]["track_id"] == 1

async def test_read_playlist_missing_raises(client: Client) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://playlists/99999")

async def test_playlist_audit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://playlists/10/audit")
    payload = json.loads(result[0].text)
    assert payload["playlist_id"] == 10
    assert payload["total_tracks"] == 3
    assert "passed" in payload and "failed" in payload
    assert isinstance(payload["per_track"], list)
    assert len(payload["per_track"]) == 3
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_playlist_resources.py -v
```
Expected: resource not found.

- [ ] **Step 3: Write `app/v2/resources/playlist.py`**

```python
"""Playlist-scoped resources."""

from __future__ import annotations

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.domain.audit.rules import audit_track
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.v2.schemas.resource_views import PlaylistAuditView
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError

@resource(
    "local://playlists/{id}{?include_tracks}",
    mime_type="application/json",
    tags={"namespace:library", "entity:playlist", "view:playlist"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def playlist_view(
    id: int,
    include_tracks: bool = False,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Playlist view. ``include_tracks=true`` embeds ordered items."""
    pl = await uow.playlists.get(id)
    if pl is None:
        raise NotFoundError("playlist", id)
    payload: dict = {
        "id": pl.id,
        "name": pl.name,
        "source_of_truth": pl.source_of_truth,
        "parent_id": pl.parent_id,
    }
    if include_tracks:
        items = await uow.playlists.get_items(id)
        payload["tracks"] = [
            {"track_id": it.track_id, "sort_index": it.sort_index} for it in items
        ]
    return json_dump(payload)

@resource(
    "local://playlists/{id}/audit",
    mime_type="application/json",
    tags={"namespace:library", "entity:playlist", "view:audit"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def playlist_audit(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Run the techno audit against every track in the playlist."""
    if await uow.playlists.get(id) is None:
        raise NotFoundError("playlist", id)
    items = await uow.playlists.get_items(id)
    per_track: list[dict] = []
    passed = 0
    failed = 0
    for it in items:
        feat = await uow.track_features.get_by_track_id(it.track_id)
        if feat is None:
            per_track.append({
                "track_id": it.track_id,
                "passed": False,
                "violations": ["no features"],
            })
            failed += 1
            continue
        rep = audit_track(feat)
        per_track.append({
            "track_id": it.track_id,
            "passed": rep.passed,
            "violations": list(rep.violations),
        })
        if rep.passed:
            passed += 1
        else:
            failed += 1
    view = PlaylistAuditView(
        playlist_id=id,
        total_tracks=len(items),
        passed=passed,
        failed=failed,
        per_track=per_track,
    )
    return view.model_dump_json()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_playlist_resources.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/playlist.py tests/v2/resources/test_playlist_resources.py
git commit -m "feat(v2): playlist resources (2 URIs)

local://playlists/{id}{?include_tracks} and .../audit. Audit runs
techno rules per-track and aggregates pass/fail counts."
```

---

## Task 9: `app/v2/resources/set.py` — set-scoped resources

**Files:**
- Create: `app/v2/resources/set.py`
- Test: `tests/v2/resources/test_set_resources.py`

Resources:
1. `local://sets/{id}/{view}` — view ∈ {summary, tracks, transitions, full}
2. `local://sets/{id}/cheatsheet{?version}`
3. `local://sets/{id}/narrative`
4. `local://sets/{id}/review`
5. `local://sets/{id}/versions/compare/{a}/{b}`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_set_resources.py
"""Set resource tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_set_summary(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/summary")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["template_name"] == "classic_60"
    assert payload["version_count"] == 1
    assert payload["latest_version_id"] == 1000

async def test_set_tracks_view(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/tracks")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["version_id"] == 1000
    assert len(payload["tracks"]) == 3

async def test_set_transitions_view(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/transitions")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert len(payload["transitions"]) == 2

async def test_set_full_view(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/full")
    payload = json.loads(result[0].text)
    assert "summary" in payload and "tracks" in payload and "transitions" in payload

async def test_set_unknown_view_raises(client: Client, seeded_db: object) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://sets/100/nonsense")

async def test_set_cheatsheet_default_version(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/cheatsheet")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["version_id"] == 1000
    assert len(payload["lines"]) == 3
    assert payload["lines"][0]["position"] == 1

async def test_set_cheatsheet_with_version(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/cheatsheet?version=1000")
    payload = json.loads(result[0].text)
    assert payload["version_id"] == 1000

async def test_set_narrative(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/narrative")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert isinstance(payload["narrative"], str)

async def test_set_review(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://sets/100/review")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert "weak_transitions" in payload and "hard_conflicts" in payload

async def test_set_versions_compare(client: Client, seeded_db: object) -> None:
    # Only 1 version seeded; compare same version → delta=0
    result = await client.read_resource("local://sets/100/versions/compare/1000/1000")
    payload = json.loads(result[0].text)
    assert payload["set_id"] == 100
    assert payload["delta"] == 0.0
    assert payload["changed_positions"] == []
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_set_resources.py -v
```

- [ ] **Step 3: Write `app/v2/resources/set.py`**

```python
"""Set-scoped resources — summary / tracks / transitions / cheatsheet /
narrative / review / versions compare."""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)
from app.v2.schemas.resource_views import (
    SetCheatsheetView,
    SetCompareView,
    SetNarrativeView,
    SetReviewView,
    SetSummaryView,
    SetTracksView,
    SetTransitionsView,
)
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError, ValidationError

SetView = Literal["summary", "tracks", "transitions", "full"]

@resource(
    "local://sets/{id}/{view}",
    mime_type="application/json",
    tags={"namespace:library", "entity:set"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_view_resource(
    id: int,
    view: str,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Sets:
    - ``view=summary``     — name, template, latest version meta
    - ``view=tracks``      — ordered items
    - ``view=transitions`` — pairwise scores
    - ``view=full``        — all three, embedded
    """
    if view not in {"summary", "tracks", "transitions", "full"}:
        raise ValidationError(
            f"unknown set view {view!r}",
            details={"allowed": ["summary", "tracks", "transitions", "full"]},
        )
    s = await uow.sets.get(id)
    if s is None:
        raise NotFoundError("set", id)
    latest = await uow.set_versions.get_latest(id)

    if view == "summary":
        v = SetSummaryView(
            set_id=s.id,
            name=s.name,
            template_name=s.template_name,
            version_count=await uow.set_versions.count_for_set(id),
            latest_version_id=latest.id if latest else None,
            latest_quality_score=latest.quality_score if latest else None,
        )
        return v.model_dump_json()

    if view == "tracks":
        if latest is None:
            return SetTracksView(set_id=s.id, version_id=0, tracks=[]).model_dump_json()
        items = await uow.set_versions.get_items(latest.id)
        tracks: list[dict] = []
        for it in items:
            track = await uow.tracks.get(it.track_id)
            tracks.append({
                "position": it.sort_index,
                "track_id": it.track_id,
                "title": track.title if track else None,
                "pinned": bool(getattr(it, "pinned", False)),
            })
        return SetTracksView(set_id=s.id, version_id=latest.id, tracks=tracks).model_dump_json()

    if view == "transitions":
        if latest is None:
            return SetTransitionsView(set_id=s.id, version_id=0, transitions=[]).model_dump_json()
        items = await uow.set_versions.get_items(latest.id)
        ordered = [it.track_id for it in sorted(items, key=lambda i: i.sort_index)]
        transitions: list[dict] = []
        for pos, (a, b) in enumerate(zip(ordered, ordered[1:], strict=False)):
            t = await uow.transitions.get_by_pair(a, b)
            transitions.append({
                "position": pos + 1,
                "from_track_id": a,
                "to_track_id": b,
                "overall": t.overall_quality if t else None,
                "hard_reject": bool(t.hard_reject) if t else None,
            })
        return SetTransitionsView(
            set_id=s.id, version_id=latest.id, transitions=transitions,
        ).model_dump_json()

    # view == "full"
    summary = await set_view_resource(id=id, view="summary", uow=uow)
    tracks = await set_view_resource(id=id, view="tracks", uow=uow)
    transitions = await set_view_resource(id=id, view="transitions", uow=uow)
    return json_dump({
        "summary": _loads(summary),
        "tracks": _loads(tracks),
        "transitions": _loads(transitions),
    })

@resource(
    "local://sets/{id}/cheatsheet{?version}",
    mime_type="application/json",
    tags={"namespace:library", "entity:set", "view:cheatsheet"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_cheatsheet(
    id: int,
    version: int | None = None,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """One-line-per-track summary for the DJ booth."""
    ver = (
        await uow.set_versions.get(version) if version is not None
        else await uow.set_versions.get_latest(id)
    )
    if ver is None or ver.set_id != id:
        raise NotFoundError("set_version", version or f"latest(set={id})")
    items = await uow.set_versions.get_items(ver.id)
    lines: list[dict] = []
    for it in sorted(items, key=lambda i: i.sort_index):
        track = await uow.tracks.get(it.track_id)
        feat = await uow.track_features.get_by_track_id(it.track_id)
        lines.append({
            "position": it.sort_index,
            "title": track.title if track else None,
            "bpm": feat.bpm if feat else None,
            "key": feat.key_code if feat else None,
            "energy": feat.integrated_lufs if feat else None,
        })
    return SetCheatsheetView(set_id=id, version_id=ver.id, lines=lines).model_dump_json()

@resource(
    "local://sets/{id}/narrative",
    mime_type="application/json",
    tags={"namespace:library", "entity:set", "view:narrative"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_narrative(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Human-readable arc narrative for the current version."""
    s = await uow.sets.get(id)
    if s is None:
        raise NotFoundError("set", id)
    latest = await uow.set_versions.get_latest(id)
    if latest is None:
        return SetNarrativeView(set_id=id, version_id=0, narrative="", phases=[]).model_dump_json()
    items = await uow.set_versions.get_items(latest.id)
    if not items:
        return SetNarrativeView(
            set_id=id, version_id=latest.id, narrative="(empty)", phases=[]
        ).model_dump_json()
    # Compact narrative: bucket tracks into 3 phases by position
    n = len(items)
    phases = [
        {"label": "warm_up", "start": 0, "end": max(0, n // 3 - 1)},
        {"label": "peak", "start": n // 3, "end": max(0, 2 * n // 3 - 1)},
        {"label": "close", "start": 2 * n // 3, "end": n - 1},
    ]
    narrative = (
        f"{n} tracks across warm_up/peak/close. Template {s.template_name or 'ad-hoc'}."
    )
    return SetNarrativeView(
        set_id=id, version_id=latest.id, narrative=narrative, phases=phases,
    ).model_dump_json()

@resource(
    "local://sets/{id}/review",
    mime_type="application/json",
    tags={"namespace:library", "entity:set", "view:review"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_review(
    id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Aggregate transition issues: weak scores, hard conflicts, overall quality."""
    latest = await uow.set_versions.get_latest(id)
    if latest is None:
        raise NotFoundError("set_version", f"latest(set={id})")
    items = sorted(await uow.set_versions.get_items(latest.id), key=lambda i: i.sort_index)
    weak: list[dict] = []
    hard: list[dict] = []
    for pos, (a, b) in enumerate(zip(items, items[1:], strict=False)):
        t = await uow.transitions.get_by_pair(a.track_id, b.track_id)
        if t is None:
            continue
        if t.hard_reject:
            hard.append({
                "position": pos + 1, "from_track_id": a.track_id,
                "to_track_id": b.track_id, "reason": t.reject_reason,
            })
        elif (t.overall_quality or 0) < 0.5:
            weak.append({
                "position": pos + 1, "score": t.overall_quality,
                "reason": "below 0.5 overall",
            })
    return SetReviewView(
        set_id=id, version_id=latest.id,
        quality_score=latest.quality_score or 0.0,
        weak_transitions=weak, hard_conflicts=hard,
    ).model_dump_json()

@resource(
    "local://sets/{id}/versions/compare/{a}/{b}",
    mime_type="application/json",
    tags={"namespace:library", "entity:set_version", "view:compare"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def set_versions_compare(
    id: int,
    a: int,
    b: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Compare two versions of the same set: quality delta + changed positions."""
    va = await uow.set_versions.get(a)
    vb = await uow.set_versions.get(b)
    if va is None or va.set_id != id:
        raise NotFoundError("set_version", a)
    if vb is None or vb.set_id != id:
        raise NotFoundError("set_version", b)
    items_a = sorted(await uow.set_versions.get_items(va.id), key=lambda i: i.sort_index)
    items_b = sorted(await uow.set_versions.get_items(vb.id), key=lambda i: i.sort_index)
    changed: list[int] = []
    for i, (x, y) in enumerate(zip(items_a, items_b, strict=False)):
        if x.track_id != y.track_id:
            changed.append(i + 1)
    return SetCompareView(
        set_id=id,
        version_a={"id": va.id, "quality_score": va.quality_score},
        version_b={"id": vb.id, "quality_score": vb.quality_score},
        delta=(vb.quality_score or 0.0) - (va.quality_score or 0.0),
        changed_positions=changed,
    ).model_dump_json()

# ── helpers ─────────────────────────────────────────────────────

def _loads(s: str) -> Any:
    import json
    return json.loads(s)
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_set_resources.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/set.py tests/v2/resources/test_set_resources.py
git commit -m "feat(v2): set-scoped resources (5 URIs)

local://sets/{id}/{summary|tracks|transitions|full}, cheatsheet{?version},
narrative, review, versions/compare/{a}/{b}. Typed Pydantic views."
```

---

## Task 10: `app/v2/resources/transition.py` — pairwise transition resources

**Files:**
- Create: `app/v2/resources/transition.py`
- Test: `tests/v2/resources/test_transition_resources.py`

Resources:
1. `local://transition/{from}/{to}/score` — on-demand scoring
2. `local://transition/{from}/{to}/explain` — human-readable explanation

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_transition_resources.py
"""Transition resource tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_transition_score_persisted(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition/1/2/score")
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["to_track_id"] == 2
    assert "overall" in payload
    assert "components" in payload
    assert "hard_reject" in payload

async def test_transition_score_missing_features_raises(client: Client) -> None:
    with pytest.raises(Exception):
        await client.read_resource("local://transition/999/888/score")

async def test_transition_explain(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition/1/2/explain")
    payload = json.loads(result[0].text)
    assert payload["from_track_id"] == 1
    assert payload["to_track_id"] == 2
    assert isinstance(payload["narrative"], str)
    assert isinstance(payload["suggestions"], list)
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_transition_resources.py -v
```

- [ ] **Step 3: Write `app/v2/resources/transition.py`**

```python
"""Pairwise transition resources."""

from __future__ import annotations

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.domain.transition.scorer import TransitionScorer
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
    TransitionExplainView,
    TransitionScoreView,
)
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError

@resource(
    "local://transition/{from_id}/{to_id}/score",
    mime_type="application/json",
    tags={"namespace:reasoning", "view:transition_score"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_score(
    from_id: int,
    to_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Compute (or read cached) a transition score for the pair.

    Strategy: prefer persisted row; fall back to live scoring using the
    pure-domain ``TransitionScorer``.
    """
    persisted = await uow.transitions.get_by_pair(from_id, to_id)
    if persisted is not None:
        return TransitionScoreView(
            from_track_id=from_id,
            to_track_id=to_id,
            overall=persisted.overall_quality or 0.0,
            hard_reject=bool(persisted.hard_reject),
            reject_reason=getattr(persisted, "reject_reason", None),
            components={
                "bpm": persisted.bpm_score or 0.0,
                "harmonic": persisted.harmonic_score or 0.0,
                "energy": persisted.energy_score or 0.0,
                "spectral": persisted.spectral_score or 0.0,
                "groove": persisted.groove_score or 0.0,
                "timbral": persisted.timbral_score or 0.0,
            },
        ).model_dump_json()

    feat_a = await uow.track_features.get_by_track_id(from_id)
    feat_b = await uow.track_features.get_by_track_id(to_id)
    if feat_a is None or feat_b is None:
        raise NotFoundError("track_features", f"{from_id} or {to_id}")
    scorer = TransitionScorer()
    score = scorer.score(feat_a.to_domain(), feat_b.to_domain())
    return TransitionScoreView(
        from_track_id=from_id,
        to_track_id=to_id,
        overall=score.total,
        hard_reject=score.hard_reject,
        reject_reason=score.reject_reason,
        components={
            "bpm": score.bpm,
            "harmonic": score.harmonic,
            "energy": score.energy,
            "spectral": score.spectral,
            "groove": score.groove,
            "timbral": score.timbral,
        },
    ).model_dump_json()

@resource(
    "local://transition/{from_id}/{to_id}/explain",
    mime_type="application/json",
    tags={"namespace:reasoning", "view:transition_explain"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_explain(
    from_id: int,
    to_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Narrative explanation of a pairwise transition."""
    feat_a = await uow.track_features.get_by_track_id(from_id)
    feat_b = await uow.track_features.get_by_track_id(to_id)
    if feat_a is None or feat_b is None:
        raise NotFoundError("track_features", f"{from_id} or {to_id}")
    scorer = TransitionScorer()
    score = scorer.score(feat_a.to_domain(), feat_b.to_domain())
    parts: list[str] = []
    parts.append(f"BPM: {feat_a.bpm:.1f} → {feat_b.bpm:.1f} (component {score.bpm:.2f}).")
    parts.append(f"Harmonic component {score.harmonic:.2f}.")
    parts.append(f"Energy component {score.energy:.2f}.")
    suggestions: list[str] = []
    if score.hard_reject:
        suggestions.append("hard reject — consider a bridge track")
    if score.harmonic < 0.55:
        suggestions.append("long blend (32 bars) over key drift")
    if score.energy < 0.4:
        suggestions.append("echo-out to soften energy gap")
    return TransitionExplainView(
        from_track_id=from_id,
        to_track_id=to_id,
        overall=score.total,
        narrative=" ".join(parts),
        suggestions=suggestions,
    ).model_dump_json()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_transition_resources.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/transition.py tests/v2/resources/test_transition_resources.py
git commit -m "feat(v2): transition score + explain resources

local://transition/{from}/{to}/{score|explain}. Score prefers persisted
rows, falls back to live TransitionScorer. Explain builds narrative +
style suggestions based on component breakdown."
```

---

## Task 11: `app/v2/resources/transition_history.py` — history resources

**Files:**
- Create: `app/v2/resources/transition_history.py`
- Test: `tests/v2/resources/test_transition_history_resources.py`

Resources:
1. `local://transition_history/best_pairs{?limit}`
2. `local://transition_history/history{?limit}`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_transition_history_resources.py
"""Transition history resources."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_best_pairs_default_limit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/best_pairs")
    payload = json.loads(result[0].text)
    assert payload["limit"] == 10
    assert isinstance(payload["pairs"], list)

async def test_best_pairs_with_limit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/best_pairs?limit=3")
    payload = json.loads(result[0].text)
    assert payload["limit"] == 3

async def test_history_default(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/history")
    payload = json.loads(result[0].text)
    assert payload["limit"] == 50  # default
    assert isinstance(payload["entries"], list)

async def test_history_with_limit(client: Client, seeded_db: object) -> None:
    result = await client.read_resource("local://transition_history/history?limit=5")
    payload = json.loads(result[0].text)
    assert payload["limit"] == 5
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_transition_history_resources.py -v
```

- [ ] **Step 3: Write `app/v2/resources/transition_history.py`**

```python
"""Transition history resources — crowd-tested pair stats + recent log."""

from __future__ import annotations

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import BestPairsView, TransitionHistoryView
from app.v2.server.di import get_uow

@resource(
    "local://transition_history/best_pairs{?limit}",
    mime_type="application/json",
    tags={"namespace:memory", "view:best_pairs"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_history_best_pairs(
    limit: int = 10,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Best-performing pairs sorted by average reaction × play count."""
    rows = await uow.transition_history.best_pairs(limit=limit)
    pairs = [
        {
            "from_track_id": r["from_track_id"],
            "to_track_id": r["to_track_id"],
            "plays": r["plays"],
            "avg_reaction": r["avg_reaction"],
        }
        for r in rows
    ]
    return BestPairsView(pairs=pairs, limit=limit).model_dump_json()

@resource(
    "local://transition_history/history{?limit}",
    mime_type="application/json",
    tags={"namespace:memory", "view:history"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def transition_history_log(
    limit: int = 50,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Recent transition log entries, most-recent first."""
    rows = await uow.transition_history.recent(limit=limit)
    entries = [
        {
            "id": r.id,
            "from_track_id": r.from_track_id,
            "to_track_id": r.to_track_id,
            "at": r.at.isoformat() if r.at else None,
            "reaction": r.reaction,
        }
        for r in rows
    ]
    return TransitionHistoryView(limit=limit, entries=entries).model_dump_json()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_transition_history_resources.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/transition_history.py tests/v2/resources/test_transition_history_resources.py
git commit -m "feat(v2): transition history resources (2 URIs)

local://transition_history/{best_pairs,history}{?limit}. Best_pairs
sorts by plays × avg_reaction; history is recent-first."
```

---

## Task 12: `app/v2/resources/session.py` — session-scoped resources

**Files:**
- Create: `app/v2/resources/session.py`
- Test: `tests/v2/resources/test_session_resources.py`

Resources:
1. `session://set-draft` — current draft
2. `session://tool-history` — tool call audit trail
3. `session://energy_trend{?n}` — recent energy samples

These read from `InMemorySessionStore` keyed by `ctx.session_id`.

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_session_resources.py
"""session:// resource tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_set_draft_empty_on_fresh_session(client: Client) -> None:
    result = await client.read_resource("session://set-draft")
    payload = json.loads(result[0].text)
    assert payload["tracks"] == []
    assert payload["template_name"] is None

async def test_set_draft_reflects_updates(client: Client, session_store: object) -> None:
    # We rely on a helper tool registered for tests that writes draft state;
    # alternatively populate session_store directly via the app state.
    sid = await client.call_tool("_test_set_session_id", {})  # helper returns current session_id
    session_store.update_draft(sid.data, tracks=[1, 2], template_name="classic_60")
    result = await client.read_resource("session://set-draft")
    payload = json.loads(result[0].text)
    assert payload["tracks"] == [1, 2]
    assert payload["template_name"] == "classic_60"

async def test_tool_history_empty_initially(client: Client) -> None:
    result = await client.read_resource("session://tool-history")
    payload = json.loads(result[0].text)
    assert payload["entries"] == []

async def test_energy_trend_default_last_n(client: Client) -> None:
    result = await client.read_resource("session://energy_trend")
    payload = json.loads(result[0].text)
    assert payload["last_n"] == 20  # default
    assert payload["samples"] == []

async def test_energy_trend_with_param(client: Client, session_store: object) -> None:
    sid_res = await client.call_tool("_test_set_session_id", {})
    sid = sid_res.data
    for v in (-10.0, -9.0, -8.0):
        session_store.append_energy(sid, v)
    result = await client.read_resource("session://energy_trend?n=2")
    payload = json.loads(result[0].text)
    assert payload["last_n"] == 2
    assert payload["samples"] == [-9.0, -8.0]
```

- [ ] **Step 2: Register a tiny helper tool for tests**

Add in `tests/v2/resources/conftest.py` — a `_test_set_session_id` tool that returns `ctx.session_id`:

```python
# Patch mcp_app fixture to add helper tool
from fastmcp import tool
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

@tool(name="_test_set_session_id", tags={"test:helper"})
async def _test_set_session_id_tool(ctx: Context = CurrentContext()) -> str:
    return ctx.session_id or "no-session"
```

Alternatively add `test_only_tools.py` near conftest and import from there.

- [ ] **Step 3: Write `app/v2/resources/session.py`**

```python
"""Session-scoped resources — draft, tool-history, energy trend.

All three read from the ``InMemorySessionStore`` keyed by the current
FastMCP ``session_id``. These resources MUST NOT be cached by
``ResponseCachingMiddleware`` — state changes per call.
"""

from __future__ import annotations

from fastmcp import resource
from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context

from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
    SessionDraftView,
    SessionEnergyTrendView,
    SessionToolHistoryView,
)
from app.v2.server.di import get_session_store
from app.v2.server.session_store import InMemorySessionStore

def _session_id(ctx: Context) -> str:
    return ctx.session_id or "anonymous"

@resource(
    "session://set-draft",
    mime_type="application/json",
    tags={"namespace:session", "view:set_draft"},
    annotations={"readOnlyHint": True, "idempotentHint": False},  # state varies
    meta=RESOURCE_META,
)
async def session_set_draft(
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Current ephemeral set draft for this session."""
    d = store.get_draft(_session_id(ctx))
    return SessionDraftView(**d).model_dump_json()

@resource(
    "session://tool-history",
    mime_type="application/json",
    tags={"namespace:session", "view:tool_history"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    meta=RESOURCE_META,
)
async def session_tool_history(
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Recent tool calls for this session."""
    sid = _session_id(ctx)
    return SessionToolHistoryView(
        session_id=sid, entries=store.get_tool_history(sid),
    ).model_dump_json()

@resource(
    "session://energy_trend{?n}",
    mime_type="application/json",
    tags={"namespace:session", "view:energy_trend"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    meta=RESOURCE_META,
)
async def session_energy_trend(
    n: int = 20,
    ctx: Context = CurrentContext(),
    store: InMemorySessionStore = Depends(get_session_store),
) -> str:
    """Last ``n`` energy samples recorded by middleware (LUFS)."""
    sid = _session_id(ctx)
    return SessionEnergyTrendView(
        last_n=n, samples=store.get_energy_samples(sid, last_n=n),
    ).model_dump_json()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_session_resources.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Update `bootstrap/middleware.py` cache policy**

Ensure `ResponseCachingMiddleware` excludes `session://` URIs. Add to existing middleware config or create if this is the first exclusion:

```python
# in app/v2/server/middleware/caching.py
EXCLUDED_READ_RESOURCE_PREFIXES: tuple[str, ...] = ("session://",)
```

- [ ] **Step 6: Commit**

```bash
git add app/v2/resources/session.py tests/v2/resources/test_session_resources.py app/v2/server/middleware/caching.py
git commit -m "feat(v2): session:// resources (3 URIs)

session://set-draft, tool-history, energy_trend{?n}. Backed by
InMemorySessionStore, excluded from ResponseCachingMiddleware so
state changes propagate per-read."
```

---

## Task 13: `app/v2/resources/schema.py` — entity + provider introspection

**Files:**
- Create: `app/v2/resources/schema.py`
- Test: `tests/v2/resources/test_schema_resources.py`

Resources:
1. `schema://entities` — index of registered entities
2. `schema://entities/{entity}` — full schema for one entity
3. `schema://providers` — index of providers
4. `schema://providers/{provider}` — full provider schema

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/resources/test_schema_resources.py
"""Schema introspection resource tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_schema_entities_index(client: Client) -> None:
    result = await client.read_resource("schema://entities")
    payload = json.loads(result[0].text)
    assert "entities" in payload
    assert "track" in payload["entities"]
    assert "playlist" in payload["entities"]

async def test_schema_entities_track(client: Client) -> None:
    result = await client.read_resource("schema://entities/track")
    payload = json.loads(result[0].text)
    assert payload["name"] == "track"
    assert "operations" in payload
    assert "presets" in payload
    assert "view_schema" in payload
    assert payload["view_schema"]["type"] == "object"

async def test_schema_entities_unknown_raises(client: Client) -> None:
    with pytest.raises(Exception):
        await client.read_resource("schema://entities/nonsense_entity")

async def test_schema_providers_index(client: Client) -> None:
    result = await client.read_resource("schema://providers")
    payload = json.loads(result[0].text)
    assert "providers" in payload
    assert "yandex" in payload["providers"]

async def test_schema_provider_yandex(client: Client) -> None:
    result = await client.read_resource("schema://providers/yandex")
    payload = json.loads(result[0].text)
    assert payload["name"] == "yandex"
    assert "entities_supported" in payload
    assert "operations" in payload
    assert payload["operations"]["search"] is True

async def test_schema_provider_unknown_raises(client: Client) -> None:
    with pytest.raises(Exception):
        await client.read_resource("schema://providers/spotify")  # not registered yet
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_schema_resources.py -v
```

- [ ] **Step 3: Write `app/v2/resources/schema.py`**

```python
"""Entity + provider schema introspection."""

from __future__ import annotations

from fastmcp import resource
from fastmcp.dependencies import Depends

from app.v2.registry.entity import EntityRegistry
from app.v2.registry.provider import ProviderRegistry
from app.v2.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.v2.schemas.resource_views import (
    SchemaEntityView,
    SchemaIndexView,
    SchemaProviderIndexView,
    SchemaProviderView,
)
from app.v2.server.di import get_provider_registry
from app.v2.shared.errors import NotFoundError

@resource(
    "schema://entities",
    mime_type="application/json",
    tags={"namespace:introspection", "view:schema_index"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_entities_index() -> str:
    """Index of all entities registered in ``EntityRegistry``."""
    return SchemaIndexView(entities=sorted(EntityRegistry.names())).model_dump_json()

@resource(
    "schema://entities/{entity}",
    mime_type="application/json",
    tags={"namespace:introspection", "view:schema_entity"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_entities_one(entity: str) -> str:
    """Full schema for one entity — ops, presets, filterable fields, JSON Schemas."""
    try:
        config = EntityRegistry.get(entity)
    except KeyError as exc:
        raise NotFoundError("entity", entity) from exc
    view = SchemaEntityView(
        name=config.name,
        operations=sorted(config.allowed_ops),
        presets={k: list(v) if v != "*" else ["*"] for k, v in config.field_presets.items()},
        default_preset=config.default_preset,
        searchable_fields=list(config.searchable_fields),
        filterable_fields={k: list(v) for k, v in config.filterable_fields.items()},
        sortable_fields=list(config.sortable_fields),
        relations=list(config.relations.keys()),
        view_schema=config.view_schema.model_json_schema(),
        filter_schema=config.filter_schema.model_json_schema(),
        create_schema=config.create_schema.model_json_schema(),
        update_schema=config.update_schema.model_json_schema(),
    )
    return view.model_dump_json()

@resource(
    "schema://providers",
    mime_type="application/json",
    tags={"namespace:introspection", "view:provider_index"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_providers_index(
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> str:
    return SchemaProviderIndexView(
        providers=sorted(registry.names()),
    ).model_dump_json()

@resource(
    "schema://providers/{provider}",
    mime_type="application/json",
    tags={"namespace:introspection", "view:provider"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def schema_provider_one(
    provider: str,
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> str:
    try:
        adapter = registry.get(provider)
    except KeyError as exc:
        raise NotFoundError("provider", provider) from exc
    entities_supported = list(getattr(adapter, "entities_supported", ["track", "album", "artist", "playlist", "likes"]))
    operations: dict[str, bool] = {
        "read": hasattr(adapter, "read"),
        "write": hasattr(adapter, "write"),
        "search": hasattr(adapter, "search"),
        "download_audio": hasattr(adapter, "download_audio"),
    }
    return SchemaProviderView(
        name=provider,
        entities_supported=entities_supported,
        operations=operations,
    ).model_dump_json()
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_schema_resources.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/schema.py tests/v2/resources/test_schema_resources.py
git commit -m "feat(v2): schema:// introspection resources (4 URIs)

schema://entities, schema://entities/{entity}, schema://providers,
schema://providers/{provider}. Reads from EntityRegistry and
ProviderRegistry; emits full Pydantic JSON Schemas."
```

---

## Task 14: `app/v2/resources/reference/camelot.py` — Camelot wheel blob

**Files:**
- Create: `app/v2/resources/reference/camelot.py`
- Test: `tests/v2/resources/test_reference_resources.py` (partial)

Static reference blob. Returns `ResourceResult([ResourceContent(...)])` per blueprint §8.4 — demonstrates the v3 multi-content pattern at least once.

- [ ] **Step 1: Write failing tests (partial — camelot slice)**

```python
# tests/v2/resources/test_reference_resources.py
"""Static reference blob tests."""

from __future__ import annotations

import json

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

async def test_reference_camelot_has_wheel(client: Client) -> None:
    result = await client.read_resource("reference://camelot")
    payload = json.loads(result[0].text)
    assert "wheel" in payload
    assert len(payload["wheel"]) == 24
    # Camelot notation sanity: first minor is "1A", last major is "12B"
    notations = {entry["camelot"] for entry in payload["wheel"]}
    assert "8A" in notations
    assert "8B" in notations
    assert result[0].mimeType == "application/json"

async def test_reference_camelot_has_distance_rules(client: Client) -> None:
    result = await client.read_resource("reference://camelot")
    payload = json.loads(result[0].text)
    assert "distance_rules" in payload
    # Rule examples: same number different letter = relative major/minor
    assert any("adjacent" in r["name"].lower() for r in payload["distance_rules"])
```

- [ ] **Step 2: Run test — expected FAIL**

```bash
uv run pytest tests/v2/resources/test_reference_resources.py -v
```

- [ ] **Step 3: Write `app/v2/resources/reference/camelot.py`**

```python
"""reference://camelot — 24-key wheel + distance rules as a static blob.

Assembled at import time from ``app.v2.domain.camelot.wheel``. The
payload is intended to prime an LLM session with Camelot semantics so
it can answer key-compatibility questions without calling tools.
"""

from __future__ import annotations

from fastmcp import resource
from fastmcp.resources import ResourceContent, ResourceResult

from app.v2.domain.camelot.wheel import CAMELOT_WHEEL, DISTANCE_RULES
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

def _build_payload() -> str:
    wheel = [
        {
            "key_code": entry.key_code,
            "pitch_class": entry.pitch_class,
            "mode": entry.mode,
            "name": entry.name,
            "camelot": entry.camelot,
        }
        for entry in CAMELOT_WHEEL
    ]
    rules = [
        {"name": r.name, "distance": r.distance, "description": r.description}
        for r in DISTANCE_RULES
    ]
    return json_dump({"wheel": wheel, "distance_rules": rules})

_PAYLOAD_JSON: str = _build_payload()

@resource(
    "reference://camelot",
    mime_type="application/json",
    tags={"namespace:reference", "view:knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def reference_camelot() -> ResourceResult:
    """Full Camelot wheel (24 keys) + distance rules.

    Returns a multi-content ResourceResult so clients that prefer
    markdown can render the ``text/markdown`` content, while
    programmatic agents parse the JSON.
    """
    md_lines = [
        "# Camelot Wheel",
        "",
        "24 keys arranged so adjacent numbers are perfect-fifths apart.",
        "",
        "| Camelot | Name | Mode |",
        "|---------|------|------|",
    ]
    for entry in CAMELOT_WHEEL:
        mode_name = "major" if entry.mode == 1 else "minor"
        md_lines.append(f"| {entry.camelot} | {entry.name} | {mode_name} |")
    markdown = "\n".join(md_lines)

    return ResourceResult(
        contents=[
            ResourceContent(content=_PAYLOAD_JSON, mime_type="application/json"),
            ResourceContent(content=markdown, mime_type="text/markdown"),
        ],
    )
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_reference_resources.py::test_reference_camelot_has_wheel tests/v2/resources/test_reference_resources.py::test_reference_camelot_has_distance_rules -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/resources/reference/camelot.py tests/v2/resources/test_reference_resources.py
git commit -m "feat(v2): reference://camelot knowledge blob

Multi-content ResourceResult (JSON + Markdown). Assembled at import
time from app/v2/domain/camelot/wheel.py. Demonstrates v3
ResourceResult pattern."
```

---

## Task 15: `app/v2/resources/reference/subgenres.py` — 15 subgenre profiles

**Files:**
- Create: `app/v2/resources/reference/subgenres.py`
- Test: extend `tests/v2/resources/test_reference_resources.py`

- [ ] **Step 1: Extend tests**

Append to `tests/v2/resources/test_reference_resources.py`:

```python
async def test_reference_subgenres_has_15(client: Client) -> None:
    result = await client.read_resource("reference://subgenres")
    payload = json.loads(result[0].text)
    assert len(payload["subgenres"]) == 15
    names = {s["name"] for s in payload["subgenres"]}
    assert {"ambient_dub", "dub_techno", "minimal", "hard_techno"}.issubset(names)

async def test_reference_subgenres_ordered_by_energy(client: Client) -> None:
    result = await client.read_resource("reference://subgenres")
    payload = json.loads(result[0].text)
    names = [s["name"] for s in payload["subgenres"]]
    assert names[0] == "ambient_dub"
    assert names[-1] == "hard_techno"

async def test_reference_subgenres_have_descriptors(client: Client) -> None:
    result = await client.read_resource("reference://subgenres")
    payload = json.loads(result[0].text)
    first = payload["subgenres"][0]
    assert "description" in first
    assert "typical_bpm" in first
    assert "typical_lufs" in first
    assert "key_features" in first
```

- [ ] **Step 2: Write `app/v2/resources/reference/subgenres.py`**

```python
"""reference://subgenres — 15 techno subgenres with discriminating features."""

from __future__ import annotations

from fastmcp import resource

from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

# Ordered low → high energy per docs/domain-glossary.md.
SUBGENRE_PROFILES: list[dict] = [
    {
        "name": "ambient_dub",
        "description": "Long, atmospheric pads; minimal kick; wide stereo image.",
        "typical_bpm": (110, 124),
        "typical_lufs": (-20, -14),
        "key_features": {"hp_ratio_high": True, "energy_mean_low": True},
    },
    {
        "name": "dub_techno",
        "description": "Chord stabs drenched in delay; deep kick; Basic Channel lineage.",
        "typical_bpm": (118, 128),
        "typical_lufs": (-18, -12),
        "key_features": {"lra_wide": True, "centroid_low": True},
    },
    {
        "name": "minimal",
        "description": "Sparse arrangement, restrained percussion, locked-groove loops.",
        "typical_bpm": (124, 130),
        "typical_lufs": (-16, -10),
        "key_features": {"kick_prominence_low": True, "spectral_flux_std_low": True},
    },
    {
        "name": "detroit",
        "description": "Soulful strings, classic 909/808 drums, warm analog lineage.",
        "typical_bpm": (126, 135),
        "typical_lufs": (-14, -9),
        "key_features": {"harmonic_content_high": True},
    },
    {
        "name": "melodic_deep",
        "description": "Emotive chord progressions, rolling sub, deep-house adjacent.",
        "typical_bpm": (120, 128),
        "typical_lufs": (-13, -8),
        "key_features": {"centroid_low": True, "tonnetz_stable": True},
    },
    {
        "name": "progressive",
        "description": "Gradual build over long arcs, layered synths, epic breakdowns.",
        "typical_bpm": (125, 132),
        "typical_lufs": (-12, -7),
        "key_features": {"energy_slope_positive": True},
    },
    {
        "name": "hypnotic",
        "description": "Repetitive micro-variation, trance-inducing loops.",
        "typical_bpm": (130, 138),
        "typical_lufs": (-11, -7),
        "key_features": {"spectral_flux_std_low": True, "variation_low": True},
    },
    {
        "name": "driving",
        "description": "Forward-moving groove, solid kick, peak-time warm-up.",
        "typical_bpm": (132, 138),
        "typical_lufs": (-10, -6),
        "key_features": {"onset_rate_high": True},
    },
    {
        "name": "tribal",
        "description": "Percussion-forward, layered congas/shakers, polyrhythmic.",
        "typical_bpm": (128, 136),
        "typical_lufs": (-12, -7),
        "key_features": {"onset_rate_very_high": True, "hp_ratio_low": True},
    },
    {
        "name": "breakbeat",
        "description": "Non-4/4 drums, chopped loops, UK-lineage.",
        "typical_bpm": (125, 140),
        "typical_lufs": (-11, -6),
        "key_features": {"spectral_flux_std_high": True, "pulse_clarity_mid": True},
    },
    {
        "name": "peak_time",
        "description": "Heavy kick, riffs, high-energy peak-room weapons.",
        "typical_bpm": (130, 138),
        "typical_lufs": (-9, -5),
        "key_features": {"kick_prominence_high": True, "energy_mean_high": True},
    },
    {
        "name": "acid",
        "description": "303 resonance, squelchy lead, cut-through attack.",
        "typical_bpm": (130, 140),
        "typical_lufs": (-10, -5),
        "key_features": {"centroid_high": True, "resonance_high": True},
    },
    {
        "name": "raw",
        "description": "Distorted textures, low-fi aesthetic, no-compromise energy.",
        "typical_bpm": (132, 145),
        "typical_lufs": (-8, -5),
        "key_features": {"crest_factor_low": True, "centroid_high": True},
    },
    {
        "name": "industrial",
        "description": "Metallic percussion, dystopian atmospheres, distorted 4/4.",
        "typical_bpm": (135, 148),
        "typical_lufs": (-8, -4),
        "key_features": {"lra_narrow": True, "centroid_high": True},
    },
    {
        "name": "hard_techno",
        "description": "Maximum BPM, crushing kicks, unrelenting energy.",
        "typical_bpm": (140, 155),
        "typical_lufs": (-7, -4),
        "key_features": {"bpm_high": True, "kick_prominence_very_high": True},
    },
]

@resource(
    "reference://subgenres",
    mime_type="application/json",
    tags={"namespace:reference", "view:knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def reference_subgenres() -> str:
    return json_dump({"subgenres": SUBGENRE_PROFILES})
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_reference_resources.py -v
```
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add app/v2/resources/reference/subgenres.py tests/v2/resources/test_reference_resources.py
git commit -m "feat(v2): reference://subgenres knowledge blob

15 subgenre profiles with description, BPM/LUFS ranges, key
discriminating features. Ordered low→high energy."
```

---

## Task 16: `app/v2/resources/reference/templates.py` — 8 set templates

**Files:**
- Create: `app/v2/resources/reference/templates.py`
- Test: extend `tests/v2/resources/test_reference_resources.py`

- [ ] **Step 1: Extend tests**

```python
async def test_reference_templates_has_8(client: Client) -> None:
    result = await client.read_resource("reference://templates")
    payload = json.loads(result[0].text)
    assert len(payload["templates"]) == 8
    names = {t["name"] for t in payload["templates"]}
    assert {"warm_up_30", "classic_60", "peak_hour_60",
            "roller_90", "progressive_120", "wave_120",
            "closing_60", "full_library"}.issubset(names)

async def test_reference_template_has_slots(client: Client) -> None:
    result = await client.read_resource("reference://templates")
    payload = json.loads(result[0].text)
    classic = next(t for t in payload["templates"] if t["name"] == "classic_60")
    assert classic["duration_minutes"] == 60
    assert "slots" in classic
    assert len(classic["slots"]) > 0
```

- [ ] **Step 2: Write `app/v2/resources/reference/templates.py`**

```python
"""reference://templates — 8 set-template definitions."""

from __future__ import annotations

from fastmcp import resource

from app.v2.domain.template.registry import SET_TEMPLATES
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

def _build_payload() -> str:
    templates: list[dict] = []
    for tpl in SET_TEMPLATES:
        templates.append({
            "name": tpl.name,
            "duration_minutes": tpl.duration_minutes,
            "description": tpl.description,
            "slots": [
                {
                    "position": slot.position,
                    "target_mood": slot.target_mood,
                    "energy_lufs": slot.energy_lufs,
                    "bpm_range": list(slot.bpm_range),
                    "target_duration_s": slot.target_duration_s,
                    "flexibility": slot.flexibility,
                }
                for slot in tpl.slots
            ],
        })
    return json_dump({"templates": templates})

_PAYLOAD: str = _build_payload()

@resource(
    "reference://templates",
    mime_type="application/json",
    tags={"namespace:reference", "view:knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def reference_templates() -> str:
    return _PAYLOAD
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_reference_resources.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/v2/resources/reference/templates.py tests/v2/resources/test_reference_resources.py
git commit -m "feat(v2): reference://templates knowledge blob

8 set-template definitions assembled from
app/v2/domain/template/registry.py. Payload pre-built at import time."
```

---

## Task 17: `app/v2/resources/reference/audit_rules.py` — techno audit rules

**Files:**
- Create: `app/v2/resources/reference/audit_rules.py`
- Test: extend `tests/v2/resources/test_reference_resources.py`

- [ ] **Step 1: Extend tests**

```python
async def test_reference_audit_rules(client: Client) -> None:
    result = await client.read_resource("reference://audit_rules")
    payload = json.loads(result[0].text)
    assert "rules" in payload
    # Should include all parameters from docs/requirements table 12
    names = {r["parameter"] for r in payload["rules"]}
    assert "bpm" in names
    assert "integrated_lufs" in names
    assert "kick_prominence" in names

async def test_reference_audit_rules_bpm_range(client: Client) -> None:
    result = await client.read_resource("reference://audit_rules")
    payload = json.loads(result[0].text)
    bpm = next(r for r in payload["rules"] if r["parameter"] == "bpm")
    assert bpm["min"] == 120
    assert bpm["max"] == 155
```

- [ ] **Step 2: Write `app/v2/resources/reference/audit_rules.py`**

```python
"""reference://audit_rules — techno audit criteria as a static blob."""

from __future__ import annotations

from fastmcp import resource

from app.v2.domain.audit.rules import TECHNO_AUDIT_SPEC
from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)

def _build_payload() -> str:
    rules: list[dict] = []
    for spec in TECHNO_AUDIT_SPEC:
        rules.append({
            "parameter": spec.parameter,
            "min": spec.minimum,
            "max": spec.maximum,
            "unit": spec.unit,
            "description": spec.description,
        })
    return json_dump({"rules": rules})

_PAYLOAD: str = _build_payload()

@resource(
    "reference://audit_rules",
    mime_type="application/json",
    tags={"namespace:reference", "view:knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
def reference_audit_rules() -> str:
    return _PAYLOAD
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/resources/test_reference_resources.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/v2/resources/reference/audit_rules.py tests/v2/resources/test_reference_resources.py
git commit -m "feat(v2): reference://audit_rules knowledge blob

Techno audit criteria from app/v2/domain/audit/rules.py exposed as
JSON. Parameter, min, max, unit, description per rule."
```

---

## Task 18: Registration check — list_resources() returns all URIs

**Files:**
- Extend: `tests/v2/resources/test_resource_registration.py`

- [ ] **Step 1: Add registration test**

Append to `tests/v2/resources/test_resource_registration.py`:

```python
from __future__ import annotations

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

EXPECTED_STATIC_URIS = {
    # Track
    "local://tracks/{id}",
    "local://tracks/{id}/features",
    "local://tracks/{id}/audit",
    "local://tracks/{id}/suggest_next{?limit,energy_direction}",
    "local://tracks/{id}/suggest_replacement/{set_id}/{position}",
    # Playlist
    "local://playlists/{id}{?include_tracks}",
    "local://playlists/{id}/audit",
    # Set
    "local://sets/{id}/{view}",
    "local://sets/{id}/cheatsheet{?version}",
    "local://sets/{id}/narrative",
    "local://sets/{id}/review",
    "local://sets/{id}/versions/compare/{a}/{b}",
    # Transition
    "local://transition/{from_id}/{to_id}/score",
    "local://transition/{from_id}/{to_id}/explain",
    # Transition history
    "local://transition_history/best_pairs{?limit}",
    "local://transition_history/history{?limit}",
    # Session (fixed URIs)
    "session://set-draft",
    "session://tool-history",
    "session://energy_trend{?n}",
    # Schema
    "schema://entities",
    "schema://entities/{entity}",
    "schema://providers",
    "schema://providers/{provider}",
    # Reference
    "reference://camelot",
    "reference://subgenres",
    "reference://templates",
    "reference://audit_rules",
}

async def test_all_expected_uris_registered(client: Client) -> None:
    resources = await client.list_resources()
    templates = await client.list_resource_templates()
    registered = {r.uri for r in resources} | {t.uriTemplate for t in templates}
    missing = EXPECTED_STATIC_URIS - registered
    assert not missing, f"Missing resource URIs: {sorted(missing)}"

async def test_all_resources_tagged(client: Client) -> None:
    resources = await client.list_resources()
    templates = await client.list_resource_templates()
    all_items = list(resources) + list(templates)
    for item in all_items:
        assert item.tags, f"resource {item.uri} has no tags"

async def test_all_resources_read_only(client: Client) -> None:
    resources = await client.list_resources()
    templates = await client.list_resource_templates()
    all_items = list(resources) + list(templates)
    for item in all_items:
        ann = getattr(item, "annotations", {}) or {}
        assert ann.get("readOnlyHint") is True, f"{item.uri} missing readOnlyHint"
```

- [ ] **Step 2: Run tests — expected PASS (all URIs are present from Tasks 7–17)**

```bash
uv run pytest tests/v2/resources/test_resource_registration.py -v
```
Expected: 3 passed (plus the 5 shared-constants tests from Task 2).

- [ ] **Step 3: Commit**

```bash
git add tests/v2/resources/test_resource_registration.py
git commit -m "test(v2): assert all 26 resource URIs are registered

Registration test verifies expected URI set against client.list_resources()
+ list_resource_templates(). Guards against silently dropped decorators."
```

---

## Task 19: `tests/v2/prompts/conftest.py` + helper

**Files:**
- Create: `tests/v2/prompts/conftest.py`

- [ ] **Step 1: Write `tests/v2/prompts/conftest.py`**

```python
"""Shared fixtures for prompt tests.

Prompts are pure functions — fixtures are minimal. We still use the
in-memory Client so we exercise the actual @prompt registration path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from fastmcp import FastMCP
from fastmcp.client import Client

@pytest_asyncio.fixture
async def mcp_app() -> AsyncIterator[FastMCP]:
    from app.v2.server.app import build_mcp_app_for_tests
    app = await build_mcp_app_for_tests()
    yield app

@pytest_asyncio.fixture
async def client(mcp_app: FastMCP) -> AsyncIterator[Client]:
    async with Client(mcp_app) as c:
        yield c
```

- [ ] **Step 2: Commit**

```bash
git add tests/v2/prompts/conftest.py
git commit -m "test(v2): prompt test fixtures"
```

---

## Task 20: `app/v2/prompts/dj_expert_session.py` — knowledge-priming prompt

**Files:**
- Create: `app/v2/prompts/dj_expert_session.py`
- Test: `tests/v2/prompts/test_dj_expert_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_dj_expert_session.py
"""dj_expert_session prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.dj_expert_session import dj_expert_session

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result_directly() -> None:
    result = dj_expert_session()
    assert isinstance(result, PromptResult)
    assert result.description is not None
    assert len(result.messages) >= 1
    assert isinstance(result.messages[0], Message)

def test_description_mentions_dj() -> None:
    result = dj_expert_session()
    assert "DJ" in (result.description or "")

def test_content_mentions_camelot_and_subgenres() -> None:
    result = dj_expert_session()
    text = " ".join(m.content.text if hasattr(m.content, "text") else str(m.content) for m in result.messages)
    assert "camelot" in text.lower() or "Camelot" in text
    assert "subgenre" in text.lower()

async def test_prompt_reachable_via_client(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "dj_expert_session" for p in prompts)

    rendered = await client.get_prompt("dj_expert_session", arguments={})
    # rendered.messages is a list of GetPromptResult messages
    assert len(rendered.messages) >= 1
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/prompts/test_dj_expert_session.py -v
```

- [ ] **Step 3: Write `app/v2/prompts/dj_expert_session.py`**

```python
"""dj_expert_session — knowledge priming recipe.

Reads ``reference://*`` blobs so the LLM acquires DJ-domain vocabulary
(Camelot, 15 subgenres, 8 templates, audit rules) in a single call.
"""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

_BODY = """You are a DJ techno set-building expert.

Load domain knowledge before planning any mix. Read these resources
once per session:

1. reference://camelot      — 24-key Camelot wheel + distance rules
2. reference://subgenres    — 15 techno subgenres (ambient_dub → hard_techno)
3. reference://templates    — 8 set templates (warm_up_30 .. full_library)
4. reference://audit_rules  — techno quality criteria (BPM, LUFS, spectral)

Apply these guidelines:
- BPM range for techno: 120–155 (sweet spot 124–132).
- Prefer Camelot distance 0–1 between adjacent tracks (same key, ±1 on wheel, or A↔B relative).
- Energy flow follows the target template's arc — don't peak too early.
- Mood transitions: stay within one step of the 15-subgenre order, or cross deliberately for contrast.

Inspect the library with entity_list / entity_get, score candidate
pairs with transition_score_pool, order with sequence_optimize, then
persist via entity_create(entity='set_version').
"""

@prompt(
    name="dj_expert_session",
    description="Prime the LLM with DJ-domain knowledge (Camelot, subgenres, templates, audit rules).",
    tags={"namespace:workflow", "priming"},
    meta=PROMPT_META,
)
def dj_expert_session() -> PromptResult:
    return PromptResult(
        messages=[Message(_BODY)],
        description="DJ Expert Session — knowledge priming for techno set building.",
    )
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_dj_expert_session.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/prompts/dj_expert_session.py tests/v2/prompts/test_dj_expert_session.py
git commit -m "feat(v2): dj_expert_session priming prompt

Single-message PromptResult pointing the LLM at reference://* blobs
for Camelot, subgenres, templates, audit rules. Sets up any downstream
set-building workflow."
```

---

## Task 21: `app/v2/prompts/build_set_workflow.py` — set-building recipe

**Files:**
- Create: `app/v2/prompts/build_set_workflow.py`
- Test: `tests/v2/prompts/test_build_set_workflow.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_build_set_workflow.py
"""build_set_workflow prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.build_set_workflow import build_set_workflow

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result() -> None:
    result = build_set_workflow(playlist_id=42)
    assert isinstance(result, PromptResult)
    assert isinstance(result.messages[0], Message)

def test_description_includes_playlist_id() -> None:
    result = build_set_workflow(playlist_id=42, template="classic_60")
    assert "42" in (result.description or "")
    assert "classic_60" in (result.description or "")

def test_body_mentions_all_steps() -> None:
    result = build_set_workflow(playlist_id=42)
    text = result.messages[0].content.text if hasattr(result.messages[0].content, "text") else str(result.messages[0].content)
    assert "entity_list" in text
    assert "entity_create" in text
    assert "transition_score_pool" in text
    assert "sequence_optimize" in text

def test_default_template_used() -> None:
    result = build_set_workflow(playlist_id=1)
    text = result.messages[0].content.text if hasattr(result.messages[0].content, "text") else str(result.messages[0].content)
    assert "classic_60" in text

async def test_prompt_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "build_set_workflow" for p in prompts)

async def test_prompt_invocable_via_client(client: Client) -> None:
    rendered = await client.get_prompt(
        "build_set_workflow", arguments={"playlist_id": 10, "template": "peak_hour_60"}
    )
    assert any(
        "10" in (getattr(m.content, "text", str(m.content)))
        for m in rendered.messages
    )
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/prompts/test_build_set_workflow.py -v
```

- [ ] **Step 3: Write `app/v2/prompts/build_set_workflow.py`**

```python
"""build_set_workflow — step-by-step recipe for building a set."""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

def _build_body(playlist_id: int, template: str) -> str:
    return f"""To build a set from playlist {playlist_id} with template '{template}':

1. Load playlist items and their track IDs:
   entity_list(entity="playlist", filters={{"id": {playlist_id}}}, include_relations=["tracks"])

2. For every track lacking analysis level >= 3, schedule analysis:
   entity_create(entity="track_features", data={{"track_ids": [...], "level": 3}})

3. Audit each track against techno criteria:
   - Read local://tracks/{{id}}/audit for each and drop any with hard violations.

4. Build the candidate pool (features projection):
   entity_list(entity="track", filters={{"id__in": [...]}}, fields="scoring")

5. Compute pairwise scores across the candidate pool:
   transition_score_pool(track_ids=[...])

6. Optimize ordering under the template arc:
   sequence_optimize(
       track_ids=[...],
       algorithm="ga",
       template="{template}",
       pair_scores=...
   )

7. Persist the ordered set as a new version:
   entity_create(entity="set_version", data={{
       "set_id": ...,
       "track_order": [...],
       "label": "v1"
   }})

8. Inspect the result:
   - Read local://sets/{{set_id}}/summary
   - Read local://sets/{{set_id}}/cheatsheet
   - Read local://sets/{{set_id}}/review  (watch for weak transitions / hard conflicts)

If any transition is flagged hard_reject, either pin surrounding tracks
and re-optimize, or inject a bridge track from the candidate pool.

Return: {{"set_id": ..., "version_id": ..., "quality_score": ...}}
"""

@prompt(
    name="build_set_workflow",
    description="Recipe for building a DJ set from a playlist end-to-end.",
    tags={"namespace:workflow", "set_building"},
    meta=PROMPT_META,
)
def build_set_workflow(playlist_id: int, template: str = "classic_60") -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(playlist_id, template))],
        description=f"Recipe: build set from playlist {playlist_id} with template '{template}'.",
    )
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_build_set_workflow.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add app/v2/prompts/build_set_workflow.py tests/v2/prompts/test_build_set_workflow.py
git commit -m "feat(v2): build_set_workflow prompt

8-step recipe: list → analyze → audit → score_pool → optimize →
persist → inspect → iterate. Parameterized by playlist_id + template."
```

---

## Task 22: `app/v2/prompts/deliver_set_workflow.py`

**Files:**
- Create: `app/v2/prompts/deliver_set_workflow.py`
- Test: `tests/v2/prompts/test_deliver_set_workflow.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_deliver_set_workflow.py
"""deliver_set_workflow tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.deliver_set_workflow import deliver_set_workflow

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result() -> None:
    result = deliver_set_workflow(set_id=100)
    assert isinstance(result, PromptResult)
    assert isinstance(result.messages[0], Message)

def test_description_has_set_id() -> None:
    result = deliver_set_workflow(set_id=100)
    assert "100" in (result.description or "")

def test_body_mentions_conflict_gate() -> None:
    result = deliver_set_workflow(set_id=100)
    text = result.messages[0].content.text if hasattr(result.messages[0].content, "text") else str(result.messages[0].content)
    assert "conflict" in text.lower() or "elicit" in text.lower()

def test_body_mentions_export_formats() -> None:
    result = deliver_set_workflow(set_id=100)
    text = result.messages[0].content.text if hasattr(result.messages[0].content, "text") else str(result.messages[0].content)
    for fmt in ("m3u8", "rekordbox", "cheatsheet"):
        assert fmt in text.lower()

async def test_prompt_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "deliver_set_workflow" for p in prompts)
```

- [ ] **Step 2: Run tests — expected FAIL**

```bash
uv run pytest tests/v2/prompts/test_deliver_set_workflow.py -v
```

- [ ] **Step 3: Write `app/v2/prompts/deliver_set_workflow.py`**

```python
"""deliver_set_workflow — export + (optional) YM sync."""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

def _build_body(set_id: int, sync_to_ym: bool) -> str:
    sync_clause = (
        "7. Sync the set to the platform as a new playlist:\n"
        "   provider_write(entity='playlist', operation='create_from_set', "
        f"params={{'set_id': {set_id}}})\n"
        if sync_to_ym
        else "7. Skip platform sync (sync_to_ym=false).\n"
    )
    return f"""To deliver set {set_id}:

1. Read the latest version summary:
   local://sets/{set_id}/summary — note version_id and quality_score.

2. Score every transition (fresh, not cached):
   transition_score_pool(track_ids=<ordered track list>)
   — writes fresh rows into the transitions table.

3. Review for hard conflicts:
   local://sets/{set_id}/review — inspect 'hard_conflicts'.

4. If hard_conflicts is non-empty:
   - Use ctx.elicit to ask the user whether to continue or abort.
   - If abort → stop; if continue → proceed.

5. Write deliverables:
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'm3u8'}})
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'rekordbox_xml'}})
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'json_guide'}})
   - local://sets/{set_id}/cheatsheet — copy contents for the DJ booth.

6. Copy MP3 files into generated-sets/<name>/ (skipped if iCloud stub).

{sync_clause}
8. Final verification:
   - local://sets/{set_id}/summary (version count increased? quality_score stable?)
   - If any export failed, report file_path=null + error for that format.

Return: {{"set_id": {set_id}, "exports": [...], "ym_playlist_id": ...}}.
"""

@prompt(
    name="deliver_set_workflow",
    description="Recipe: export a set (+ optional YM sync) with a conflict gate.",
    tags={"namespace:workflow", "delivery"},
    meta=PROMPT_META,
)
def deliver_set_workflow(set_id: int, sync_to_ym: bool = False) -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(set_id, sync_to_ym))],
        description=f"Recipe: deliver set {set_id} (sync_to_ym={sync_to_ym}).",
    )
```

- [ ] **Step 4: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_deliver_set_workflow.py -v
```

- [ ] **Step 5: Commit**

```bash
git add app/v2/prompts/deliver_set_workflow.py tests/v2/prompts/test_deliver_set_workflow.py
git commit -m "feat(v2): deliver_set_workflow prompt

8-step recipe: score → review → elicit on conflicts → export M3U8 /
Rekordbox XML / JSON guide / cheatsheet → copy files → (opt) sync YM."
```

---

## Task 23: `app/v2/prompts/expand_playlist_workflow.py`

**Files:**
- Create: `app/v2/prompts/expand_playlist_workflow.py`
- Test: `tests/v2/prompts/test_expand_playlist_workflow.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_expand_playlist_workflow.py
"""expand_playlist_workflow tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.expand_playlist_workflow import expand_playlist_workflow

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result() -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=50)
    assert isinstance(r, PromptResult)
    assert isinstance(r.messages[0], Message)

def test_description_has_target_count() -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=50)
    assert "50" in (r.description or "")

def test_body_mentions_provider_search(capsys) -> None:
    r = expand_playlist_workflow(playlist_id=10, target_count=20)
    text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
    assert "provider_search" in text or "provider_read" in text
    assert "track_features" in text
    assert "classify_mood" in text or "mood" in text

async def test_prompt_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "expand_playlist_workflow" for p in prompts)
```

- [ ] **Step 2: Write `app/v2/prompts/expand_playlist_workflow.py`**

```python
"""expand_playlist_workflow — audit → discover → import → analyze → classify."""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

def _body(playlist_id: int, target_count: int) -> str:
    return f"""To expand playlist {playlist_id} to ~{target_count} tracks:

1. Audit current state:
   local://playlists/{playlist_id}/audit — count pass/fail.
   local://playlists/{playlist_id}?include_tracks=true — current track IDs.

2. For each failing track, optionally remove or keep flagged.

3. Pick 3–5 seed tracks (high-quality, diverse mood from audit pass list).

4. Discover similar tracks per seed:
   provider_search(query=<seed title/artist>, type='tracks', limit=20)
   OR
   provider_read(entity='similar_tracks', id=<provider_track_id>, params={{'limit': 20}})

5. Filter candidates against feedback memory (if available):
   - Skip tracks already on entity_list(entity='track_feedback', filters={{'banned': True}})

6. Import new provider tracks that aren't in the library yet:
   entity_create(entity='track', data={{'provider': 'yandex', 'provider_ids': [...]}})
   — handler fetches metadata + creates rows + links playlist.

7. Download MP3s for newly-imported tracks:
   entity_create(entity='audio_file', data={{'track_ids': [...]}})
   — handler downloads + writes file + registers DjLibraryItem.

8. Analyze all newly-downloaded tracks at L3:
   entity_create(entity='track_features', data={{'track_ids': [...], 'level': 3}})

9. Classify mood for everything:
   entity_update(entity='track_features', data={{'track_ids': [...], 'action': 'classify_mood'}})

10. Re-audit:
    local://playlists/{playlist_id}/audit — verify pass rate improved.

Return: {{"playlist_id": {playlist_id}, "added_tracks": N, "final_count": N}}.
"""

@prompt(
    name="expand_playlist_workflow",
    description="Recipe: grow a playlist via provider discovery + import + analyze.",
    tags={"namespace:workflow", "discovery"},
    meta=PROMPT_META,
)
def expand_playlist_workflow(playlist_id: int, target_count: int = 100) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, target_count))],
        description=f"Recipe: expand playlist {playlist_id} toward {target_count} tracks.",
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_expand_playlist_workflow.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/v2/prompts/expand_playlist_workflow.py tests/v2/prompts/test_expand_playlist_workflow.py
git commit -m "feat(v2): expand_playlist_workflow prompt

10-step recipe: audit → seed → provider_search → feedback filter →
import → download → analyze → classify → re-audit."
```

---

## Task 24: `app/v2/prompts/full_pipeline.py`

**Files:**
- Create: `app/v2/prompts/full_pipeline.py`
- Test: `tests/v2/prompts/test_full_pipeline.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_full_pipeline.py
"""full_pipeline prompt tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.full_pipeline import full_pipeline

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result() -> None:
    r = full_pipeline(playlist_id=10, template="classic_60")
    assert isinstance(r, PromptResult)

def test_body_chains_three_workflows() -> None:
    r = full_pipeline(playlist_id=10, template="classic_60")
    text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
    assert "expand_playlist_workflow" in text
    assert "build_set_workflow" in text
    assert "deliver_set_workflow" in text

def test_description_mentions_pipeline() -> None:
    r = full_pipeline(playlist_id=10)
    assert "pipeline" in (r.description or "").lower()

async def test_prompt_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "full_pipeline" for p in prompts)
```

- [ ] **Step 2: Write `app/v2/prompts/full_pipeline.py`**

```python
"""full_pipeline — chain expand + build + deliver."""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

def _body(playlist_id: int, template: str, sync_to_ym: bool) -> str:
    return f"""End-to-end pipeline from playlist {playlist_id} to a delivered set:

Stage 1: Grow the playlist
   Invoke the ``expand_playlist_workflow`` prompt with
   playlist_id={playlist_id}, target_count >= 50. Execute its 10 steps.

Stage 2: Build the set
   Invoke ``build_set_workflow`` with playlist_id={playlist_id},
   template='{template}'. Execute its 8 steps. Capture the returned
   set_id.

Stage 3: Deliver
   Invoke ``deliver_set_workflow`` with set_id=<captured>,
   sync_to_ym={'true' if sync_to_ym else 'false'}. Execute its 8 steps.

Guardrails:
- If expand failed to reach the candidate pool size, stop and report.
- If build returned quality_score < 0.5, call rebuild/sequence_optimize
  once with tighter constraints before proceeding to deliver.
- If deliver hits a hard conflict, ALWAYS elicit before exporting.

Return: {{"playlist_id": {playlist_id}, "set_id": ..., "version_id": ...,
         "quality_score": ..., "exports": [...]}}.
"""

@prompt(
    name="full_pipeline",
    description="Chain expand → build → deliver into a single pipeline.",
    tags={"namespace:workflow", "pipeline"},
    meta=PROMPT_META,
)
def full_pipeline(
    playlist_id: int,
    template: str = "classic_60",
    sync_to_ym: bool = False,
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, template, sync_to_ym))],
        description=(
            f"Full pipeline: expand playlist {playlist_id} → build set "
            f"({template}) → deliver (sync_to_ym={sync_to_ym})."
        ),
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_full_pipeline.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/v2/prompts/full_pipeline.py tests/v2/prompts/test_full_pipeline.py
git commit -m "feat(v2): full_pipeline prompt chaining expand → build → deliver"
```

---

## Task 25: `app/v2/prompts/quick_mix_check.py`

**Files:**
- Create: `app/v2/prompts/quick_mix_check.py`
- Test: `tests/v2/prompts/test_quick_mix_check.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/v2/prompts/test_quick_mix_check.py
"""quick_mix_check tests."""

from __future__ import annotations

import pytest
from fastmcp.client import Client
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts.quick_mix_check import quick_mix_check

pytestmark = pytest.mark.asyncio

def test_returns_prompt_result() -> None:
    r = quick_mix_check(track_a_id=1, track_b_id=2)
    assert isinstance(r, PromptResult)
    assert isinstance(r.messages[0], Message)

def test_body_mentions_score_resource() -> None:
    r = quick_mix_check(track_a_id=1, track_b_id=2)
    text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
    assert "local://transition/1/2/score" in text
    assert "local://transition/1/2/explain" in text

def test_description_mentions_pair() -> None:
    r = quick_mix_check(track_a_id=1, track_b_id=2)
    assert "1" in (r.description or "") and "2" in (r.description or "")

def test_explicit_direction() -> None:
    # Ensure "from" precedes "to" in both URI positions
    r = quick_mix_check(track_a_id=99, track_b_id=42)
    text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
    assert "99/42" in text

async def test_prompt_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    assert any(p.name == "quick_mix_check" for p in prompts)
```

- [ ] **Step 2: Write `app/v2/prompts/quick_mix_check.py`**

```python
"""quick_mix_check — pair compatibility shortcut."""

from __future__ import annotations

from fastmcp import prompt
from fastmcp.prompts import Message, PromptResult

from app.v2.prompts._shared import PROMPT_META

def _body(a: int, b: int) -> str:
    return f"""Quickly assess the {a} → {b} transition:

1. Ensure both tracks have features at analysis_level >= 3:
   - local://tracks/{a}/features   (expect bpm, key, lufs, energy)
   - local://tracks/{b}/features

2. Read the pairwise score:
   local://transition/{a}/{b}/score
   — components: bpm, harmonic, energy, spectral, groove, timbral.
   — flags: hard_reject, reject_reason.

3. Read the narrative explanation:
   local://transition/{a}/{b}/explain

4. Interpret:
   - overall >= 0.75 → smooth, bass-swap 8 bars.
   - 0.50 <= overall < 0.75 → long blend 32 bars or EQ-trade.
   - overall < 0.50 → echo-out or filter-sweep; consider a bridge track.
   - hard_reject=True → do NOT mix; find a bridge (2-hop chain via suggest_next).

Return: {{"from": {a}, "to": {b}, "overall": ..., "hard_reject": ...,
         "style": ...,  "suggestion": ...}}.
"""

@prompt(
    name="quick_mix_check",
    description="Inspect a single pairwise mix compatibility (a → b).",
    tags={"namespace:workflow", "reasoning"},
    meta=PROMPT_META,
)
def quick_mix_check(track_a_id: int, track_b_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(track_a_id, track_b_id))],
        description=f"Quick mix check: {track_a_id} → {track_b_id}.",
    )
```

- [ ] **Step 3: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_quick_mix_check.py -v
```

- [ ] **Step 4: Commit**

```bash
git add app/v2/prompts/quick_mix_check.py tests/v2/prompts/test_quick_mix_check.py
git commit -m "feat(v2): quick_mix_check prompt

Pair compatibility shortcut: features → score → explain → style
suggestion. Parameters are two track IDs."
```

---

## Task 26: Registration check — list_prompts() returns all 6 prompts

**Files:**
- Extend: `tests/v2/prompts/test_prompt_registration.py`

- [ ] **Step 1: Add aggregate registration tests**

Append to `tests/v2/prompts/test_prompt_registration.py`:

```python
from __future__ import annotations

import pytest
from fastmcp.client import Client

pytestmark = pytest.mark.asyncio

EXPECTED_PROMPTS = {
    "dj_expert_session",
    "build_set_workflow",
    "deliver_set_workflow",
    "expand_playlist_workflow",
    "full_pipeline",
    "quick_mix_check",
}

async def test_all_expected_prompts_registered(client: Client) -> None:
    prompts = await client.list_prompts()
    names = {p.name for p in prompts}
    missing = EXPECTED_PROMPTS - names
    assert not missing, f"Missing prompts: {sorted(missing)}"

async def test_all_prompts_have_tags(client: Client) -> None:
    prompts = await client.list_prompts()
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        assert p.tags, f"prompt {p.name} has no tags"

async def test_all_prompts_have_description(client: Client) -> None:
    prompts = await client.list_prompts()
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        assert p.description, f"prompt {p.name} has no description"

async def test_all_prompts_carry_meta_version(client: Client) -> None:
    prompts = await client.list_prompts()
    for p in prompts:
        if p.name not in EXPECTED_PROMPTS:
            continue
        meta = getattr(p, "meta", {}) or {}
        assert "version" in meta, f"prompt {p.name} meta has no 'version'"
```

- [ ] **Step 2: Run tests — expected PASS**

```bash
uv run pytest tests/v2/prompts/test_prompt_registration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/v2/prompts/test_prompt_registration.py
git commit -m "test(v2): assert all 6 prompts registered with tags + meta"
```

---

## Task 27: Wire resource + prompt modules into server app

**Files:**
- Modify: `app/v2/server/app.py` (`build_mcp_app_for_tests`)

Ensure FileSystemProvider roots include `app/v2/resources/` and `app/v2/prompts/` so decorators are picked up. If the Phase 5 server builder isn't yet in place, add a minimal `build_mcp_app_for_tests()` that eagerly imports the resource + prompt modules.

- [ ] **Step 1: Ensure `app/v2/server/app.py` has `build_mcp_app_for_tests()`**

If the function does not exist (Phase 5 not done yet), add:

```python
# app/v2/server/app.py

from __future__ import annotations

from fastmcp import FastMCP

from app.v2.server.di import configure_di_for_tests

async def build_mcp_app_for_tests() -> FastMCP:
    """Minimal FastMCP app used only in tests/v2/*.

    Eagerly imports every resource + prompt module so their decorators run.
    Do NOT use this in production — Phase 5 introduces the full builder.
    """
    app = FastMCP(name="dj-music-v2-test")
    configure_di_for_tests(app)

    # Force registration of all @resource decorators
    from app.v2.resources import (  # noqa: F401 — import for side effects
        playlist,
        schema,
        session,
        set as set_res,
        track,
        transition,
        transition_history,
    )
    from app.v2.resources.reference import (  # noqa: F401
        audit_rules,
        camelot,
        subgenres,
        templates,
    )

    # Force registration of all @prompt decorators
    from app.v2.prompts import (  # noqa: F401
        build_set_workflow,
        deliver_set_workflow,
        dj_expert_session,
        expand_playlist_workflow,
        full_pipeline,
        quick_mix_check,
    )

    # Register any test-only helper tools (session_id echo for session:// tests)
    from tests.v2.resources._test_tools import register_test_tools
    register_test_tools(app)

    return app
```

- [ ] **Step 2: Create `tests/v2/resources/_test_tools.py`**

```python
"""Test-only helper tools."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.dependencies import CurrentContext

def register_test_tools(app: FastMCP) -> None:
    @app.tool(name="_test_set_session_id", tags={"test:helper"})
    async def _return_session_id(ctx: Context = CurrentContext()) -> str:
        return ctx.session_id or "anonymous"
```

- [ ] **Step 3: Run the full Phase 4 test suite**

```bash
uv run pytest tests/v2/resources tests/v2/prompts tests/v2/schemas/test_resource_views.py -v
```
Expected: all tests pass (approximate count: 23 + 5 + 3 + 7 + 4 + 10 + 3 + 4 + 5 + 6 + 5 + 3 + 4 + 4 + 6 + 4 + 5 + 4 = 105+).

- [ ] **Step 4: Commit**

```bash
git add app/v2/server/app.py tests/v2/resources/_test_tools.py
git commit -m "feat(v2): wire resources+prompts into build_mcp_app_for_tests

Eager import side-effect decorators; register a test-only session_id
echo tool for session:// resource tests."
```

---

## Task 28: Add resources + prompts import-linter contracts

**Files:**
- Modify: `.importlinter`

- [ ] **Step 1: Append new contracts**

Add under the existing `[importlinter:contract:*]` blocks:

```ini
# ── Resources thin (same rules as tools) ──────────────
[importlinter:contract:resources-no-tools]
name = Resources must not import tools or providers directly
type = forbidden
source_modules =
    app.v2.resources
forbidden_modules =
    app.v2.tools
    app.v2.providers.yandex

# ── Prompts pure ──────────────────────────────────────
[importlinter:contract:prompts-pure]
name = Prompts must not import repositories, tools, providers, or DB
type = forbidden
source_modules =
    app.v2.prompts
forbidden_modules =
    app.v2.repositories
    app.v2.tools
    app.v2.providers
    app.v2.db
    sqlalchemy
    httpx
```

- [ ] **Step 2: Run linter**

```bash
uv run lint-imports
```
Expected: all contracts pass.

- [ ] **Step 3: Commit**

```bash
git add .importlinter
git commit -m "chore(v2): add resources-no-tools + prompts-pure linter contracts

Prompts are pure text builders; resources dispatch via registries +
repositories but never into tools or provider adapters directly."
```

---

## Task 29: Full Phase 4 verification

- [ ] **Step 1: Run entire v2 test suite**

```bash
uv run pytest tests/v2 -v
```
Expected: all tests pass.

- [ ] **Step 2: Run static checks**

```bash
uv run ruff check app/v2/resources app/v2/prompts app/v2/schemas/resource_views.py \
                  app/v2/server/session_store.py tests/v2/resources tests/v2/prompts
uv run mypy app/v2/resources app/v2/prompts app/v2/schemas/resource_views.py \
            app/v2/server/session_store.py
uv run lint-imports
```
Expected: all clean.

- [ ] **Step 3: Spot-check URI template coverage via a manual client call**

```bash
uv run python -c "
import asyncio
from fastmcp.client import Client
from app.v2.server.app import build_mcp_app_for_tests

async def main():
    app = await build_mcp_app_for_tests()
    async with Client(app) as c:
        resources = await c.list_resources()
        templates = await c.list_resource_templates()
        prompts = await c.list_prompts()
        print('resources:', len(resources))
        print('templates:', len(templates))
        print('prompts:', len(prompts))
asyncio.run(main())
"
```
Expected: `resources` + `templates` sum to 26, `prompts` = 6.

- [ ] **Step 4: Update CHANGELOG.md under `[Unreleased]`**

```markdown
### Added

- Phase 4 of blueprint refactor: 26 MCP resources and 6 workflow prompts
  under `app/v2/resources/` and `app/v2/prompts/`.
- `InMemorySessionStore` for `session://*` state.
- `SchemaEntityView` + `SchemaProviderView` Pydantic views for introspection.
- Two new import-linter contracts: resources-no-tools, prompts-pure.
```

- [ ] **Step 5: Commit + final summary**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG Phase 4 entry (resources + prompts)"
```

Final sanity: open `tests/v2/resources/test_resource_registration.py::test_all_expected_uris_registered` — the assertion set must list all 26 URIs from the blueprint §8 verbatim.

---

## Summary

### Resource URIs registered (26 total)

- `local://tracks/{id}`
- `local://tracks/{id}/features`
- `local://tracks/{id}/audit`
- `local://tracks/{id}/suggest_next{?limit,energy_direction}`
- `local://tracks/{id}/suggest_replacement/{set_id}/{position}`
- `local://playlists/{id}{?include_tracks}`
- `local://playlists/{id}/audit`
- `local://sets/{id}/{view}`
- `local://sets/{id}/cheatsheet{?version}`
- `local://sets/{id}/narrative`
- `local://sets/{id}/review`
- `local://sets/{id}/versions/compare/{a}/{b}`
- `local://transition/{from_id}/{to_id}/score`
- `local://transition/{from_id}/{to_id}/explain`
- `local://transition_history/best_pairs{?limit}`
- `local://transition_history/history{?limit}`
- `session://set-draft`
- `session://tool-history`
- `session://energy_trend{?n}`
- `schema://entities`
- `schema://entities/{entity}`
- `schema://providers`
- `schema://providers/{provider}`
- `reference://camelot`
- `reference://subgenres`
- `reference://templates`
- `reference://audit_rules`

### Prompts registered (6 total)

- `dj_expert_session`
- `build_set_workflow`
- `deliver_set_workflow`
- `expand_playlist_workflow`
- `full_pipeline`
- `quick_mix_check`

### Exit criteria

- `uv run pytest tests/v2` — all Phase 4 tests green alongside Phase 1–3 suites.
- `uv run ruff check app/v2 tests/v2` — clean.
- `uv run mypy app/v2` — clean.
- `uv run lint-imports` — all 11 contracts pass (9 prior + 2 new).
- `client.list_resources() ∪ client.list_resource_templates()` covers every URI in `EXPECTED_STATIC_URIS`.
- `client.list_prompts()` returns every name in `EXPECTED_PROMPTS`.
- `session://*` URIs return live state from `InMemorySessionStore`.
- All returned resource payloads are `str | bytes | ResourceResult` (v3 requirement); no dict/list leaks.
- All prompt returns are `fastmcp.prompts.PromptResult` with `messages: list[Message]` (never `mcp.types.PromptMessage`).
