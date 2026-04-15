# Declarative MCP — DJ Expert AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add knowledge resources, a session initialization prompt, and two atomic tools so any AI connecting to the MCP immediately operates as an expert DJ without requiring technical prompting.

**Architecture:** Three independent layers — static knowledge resources (`knowledge://`, `library://snapshot`), a session boot prompt (`dj_expert_session`), and two read-only tools (`get_candidate_pool`, `preview_set_arc`). All six files are additive; no existing code is modified except `app/controllers/tools/sets.py`.

**Tech Stack:** FastMCP v3.x `@resource` / `@tool` / `@prompt`, SQLAlchemy async, Pydantic v2, `compute_fitness` + `TransitionScorer` (existing), pytest + FastMCP `Client`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/controllers/resources/knowledge.py` | Create | 4 static `knowledge://` resources — vocabulary, subgenre culture, set dynamics, dancefloor psychology |
| `app/controllers/resources/snapshot.py` | Create | `library://snapshot` — mood distribution + playlists + last-analyzed timestamp |
| `app/controllers/prompts/workflows/dj_expert_session.py` | Create | `dj_expert_session` prompt — boots the AI as a DJ expert |
| `app/optimization/preview.py` | Create | Pure `preview_arc()` — fitness + per-pair scoring, no I/O |
| `app/controllers/tools/candidate_pool.py` | Create | `get_candidate_pool` tool — read-only library exploration |
| `app/controllers/tools/sets.py` | Modify | Add `preview_set_arc` tool wrapping `app.optimization.preview` |
| `tests/test_resources/test_knowledge.py` | Create | Tests for all 4 `knowledge://` resources |
| `tests/test_resources/test_snapshot.py` | Create | Tests for `library://snapshot` |
| `tests/test_prompts/test_dj_expert_session.py` | Create | Tests for `dj_expert_session` prompt structure |
| `tests/test_optimization/test_preview.py` | Create | Pure unit tests for `preview_arc()` |
| `tests/test_tools/test_candidate_pool.py` | Create | Integration tests for `get_candidate_pool` and `preview_set_arc` tools |

---

## Task 1: Static Knowledge Resources

**Files:**
- Create: `app/controllers/resources/knowledge.py`
- Test: `tests/test_resources/test_knowledge.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resources/test_knowledge.py
"""Tests for knowledge:// static resources."""
from __future__ import annotations

import json

import pytest

from app.controllers.resources.knowledge import (
    dancefloor_psychology,
    set_dynamics,
    subgenre_culture,
    vocabulary,
)
from app.core.constants import TechnoSubgenre

@pytest.mark.asyncio
async def test_vocabulary_covers_all_15_subgenres():
    result = await vocabulary()
    data = json.loads(result)
    # Every TechnoSubgenre.value must appear in at least one entry's subgenres list
    all_subgenres_in_vocab: set[str] = set()
    for entry in data["vocabulary"]:
        all_subgenres_in_vocab.update(entry["subgenres"])
    for sg in TechnoSubgenre:
        assert sg.value in all_subgenres_in_vocab, f"{sg.value} missing from vocabulary"

@pytest.mark.asyncio
async def test_vocabulary_has_required_fields():
    result = await vocabulary()
    data = json.loads(result)
    assert "vocabulary" in data
    assert "time_of_night" in data
    for entry in data["vocabulary"]:
        assert "term" in entry
        assert "subgenres" in entry
        assert "bpm_range" in entry
        assert "key_features" in entry

@pytest.mark.asyncio
async def test_subgenre_culture_covers_all_15():
    result = await subgenre_culture()
    data = json.loads(result)
    names = {entry["name"] for entry in data["subgenres"]}
    for sg in TechnoSubgenre:
        assert sg.value in names, f"{sg.value} missing from subgenre_culture"

@pytest.mark.asyncio
async def test_subgenre_culture_entry_fields():
    result = await subgenre_culture()
    data = json.loads(result)
    for entry in data["subgenres"]:
        assert "name" in entry
        assert "artists" in entry
        assert "set_position" in entry
        assert "flows_from" in entry
        assert "flows_into" in entry

@pytest.mark.asyncio
async def test_set_dynamics_has_required_sections():
    result = await set_dynamics()
    data = json.loads(result)
    assert "twenty_minute_rule" in data
    assert "energy_arc" in data
    assert "tension_release_cycles" in data
    assert "hard_rules" in data
    assert "phrase_awareness" in data

@pytest.mark.asyncio
async def test_dancefloor_psychology_has_required_sections():
    result = await dancefloor_psychology()
    data = json.loads(result)
    assert "crowd_states" in data
    assert "energy_recovery" in data
    assert "harmonic_mixing_perception" in data
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_resources/test_knowledge.py -v
```
Expected: `ImportError: cannot import name 'vocabulary' from 'app.controllers.resources.knowledge'`

- [ ] **Step 3: Implement knowledge resources**

Create `app/controllers/resources/knowledge.py`:

```python
"""Knowledge resources — static DJ expertise for session initialization.

Resources:
- knowledge://vocabulary — human descriptor → subgenre/BPM/feature map
- knowledge://subgenre-culture — artists, set position, transition neighbors per subgenre
- knowledge://set-dynamics — DJ set construction theory
- knowledge://dancefloor-psychology — crowd response patterns
"""

from __future__ import annotations

import json

from fastmcp.resources import resource

from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_REFERENCE,
    RESOURCE_META,
)

@resource(
    uri="knowledge://vocabulary",
    name="DJ Vocabulary",
    title="DJ Vocabulary Map",
    description=(
        "Maps human descriptors (dark, driving, hypnotic) to subgenres, "
        "BPM ranges, and audio features. Use this to translate user intent "
        "into technical filter parameters without asking the user."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
)
async def vocabulary() -> str:
    """Get vocabulary map from human descriptors to technical parameters."""
    data = {
        "vocabulary": [
            {
                "term": "dark",
                "subgenres": ["detroit", "industrial", "raw"],
                "bpm_range": "128-140",
                "key_features": [
                    "kick_prominence > 0.6",
                    "low harmonic-to-percussive ratio",
                    "high spectral centroid",
                    "atonality",
                ],
            },
            {
                "term": "hard",
                "subgenres": ["peak_time", "hard_techno", "industrial"],
                "bpm_range": "134-145",
                "key_features": [
                    "energy_mean > 0.7",
                    "high kick prominence",
                    "LUFS > -11",
                ],
            },
            {
                "term": "hypnotic",
                "subgenres": ["hypnotic", "minimal", "detroit"],
                "bpm_range": "128-135",
                "key_features": [
                    "low spectral_flux_std (repetitive loops)",
                    "onset_rate 2-4 per second",
                    "high pulse_clarity",
                ],
            },
            {
                "term": "acid",
                "subgenres": ["acid"],
                "bpm_range": "128-138",
                "key_features": [
                    "spectral_centroid > 3000 Hz",
                    "high spectral_flux_mean",
                    "TB-303 character",
                ],
            },
            {
                "term": "melodic",
                "subgenres": ["melodic_deep", "progressive"],
                "bpm_range": "126-134",
                "key_features": [
                    "harmonic-to-percussive ratio > 2.0",
                    "key_confidence > 0.7",
                    "strong harmonic content",
                ],
            },
            {
                "term": "atmospheric",
                "subgenres": ["ambient_dub", "dub_techno"],
                "bpm_range": "120-132",
                "key_features": [
                    "energy_mean < 0.3",
                    "wide stereo field",
                    "low kick prominence",
                ],
            },
            {
                "term": "driving",
                "subgenres": ["driving", "tribal", "peak_time"],
                "bpm_range": "130-140",
                "key_features": [
                    "kick_prominence > 0.5",
                    "high pulse_clarity",
                    "propulsive groove",
                ],
            },
            {
                "term": "groovy",
                "subgenres": ["tribal", "breakbeat"],
                "bpm_range": "128-136",
                "key_features": [
                    "high onset_rate",
                    "syncopated kick pattern",
                    "complex rhythms",
                ],
            },
            {
                "term": "raw",
                "subgenres": ["raw", "industrial"],
                "bpm_range": "132-145",
                "key_features": [
                    "high crest_factor",
                    "low spectral_flatness",
                    "distorted spectral character",
                ],
            },
            {
                "term": "deep",
                "subgenres": ["dub_techno", "minimal"],
                "bpm_range": "124-132",
                "key_features": [
                    "low spectral centroid",
                    "wide stereo",
                    "LRA > 10 LU",
                    "sub-bass presence",
                ],
            },
        ],
        "time_of_night": [
            {
                "window": "23:00-01:00",
                "phase": "warm_up",
                "templates": ["warm_up_30", "classic_60"],
                "energy_guidance": "Start gentle. The 20-minute rule applies — crowds need time.",
            },
            {
                "window": "01:00-03:00",
                "phase": "build",
                "templates": ["classic_60", "roller_90"],
                "energy_guidance": "Escalate gradually. Introduce peak-time tracks after 02:00.",
            },
            {
                "window": "03:00-05:00",
                "phase": "peak",
                "templates": ["peak_hour_60", "roller_90"],
                "energy_guidance": "Full energy. Hard, driving, industrial. LUFS -10 to -9.",
            },
            {
                "window": "05:00+",
                "phase": "closing",
                "templates": ["closing_60"],
                "energy_guidance": "Sunrise closing. Atmospheric, melodic, emotional resolution.",
            },
        ],
    }
    return json.dumps(data, indent=2)

@resource(
    uri="knowledge://subgenre-culture",
    name="Subgenre Culture",
    title="Techno Subgenre Culture",
    description=(
        "Cultural layer for all 15 subgenres: key artists/labels, typical set position, "
        "and compatible transition neighbors. Complements reference://subgenres "
        "which provides BPM ranges and audio features."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
)
async def subgenre_culture() -> str:
    """Get cultural metadata for all 15 techno subgenres."""
    data = {
        "note": (
            "flows_from / flows_into derived from Camelot compatibility + "
            "energy adjacency (reference://subgenres energy_level ordering)."
        ),
        "subgenres": [
            {
                "name": "ambient_dub",
                "artists": ["Basic Channel", "Gas", "Deepchord", "Rod Modell"],
                "labels": ["Basic Channel", "Echospace"],
                "set_position": "opener",
                "flows_from": [],
                "flows_into": ["dub_techno", "melodic_deep"],
            },
            {
                "name": "dub_techno",
                "artists": ["Basic Channel", "Maurizio", "Deepchord", "Varg"],
                "labels": ["Basic Channel", "Echospace", "Stroboscopic Artefacts"],
                "set_position": "early",
                "flows_from": ["ambient_dub"],
                "flows_into": ["minimal", "detroit", "melodic_deep"],
            },
            {
                "name": "minimal",
                "artists": ["Ricardo Villalobos", "Richie Hawtin", "Plastikman", "Zip"],
                "labels": ["M-nus", "Perlon", "Cocoon"],
                "set_position": "early-to-mid",
                "flows_from": ["dub_techno", "ambient_dub"],
                "flows_into": ["detroit", "hypnotic", "progressive"],
            },
            {
                "name": "detroit",
                "artists": [
                    "Underground Resistance", "Jeff Mills", "Robert Hood", "Surgeon",
                ],
                "labels": ["Underground Resistance", "Axis", "Tresor"],
                "set_position": "mid-to-peak",
                "flows_from": ["melodic_deep", "dub_techno", "minimal"],
                "flows_into": ["industrial", "peak_time", "acid"],
            },
            {
                "name": "melodic_deep",
                "artists": ["Blawan", "Objekt", "Rrose", "Shifted"],
                "labels": ["Hessle Audio", "Eaux", "Avian"],
                "set_position": "early-to-mid",
                "flows_from": ["ambient_dub", "dub_techno"],
                "flows_into": ["detroit", "progressive", "minimal"],
            },
            {
                "name": "progressive",
                "artists": ["Sasha", "John Digweed", "Nick Muir", "Bedrock"],
                "labels": ["Bedrock", "Global Underground"],
                "set_position": "mid",
                "flows_from": ["minimal", "melodic_deep"],
                "flows_into": ["detroit", "driving", "hypnotic"],
            },
            {
                "name": "hypnotic",
                "artists": ["Regis", "Drumcell", "Phase", "Alignment"],
                "labels": ["Downwards", "Machine", "Alignment"],
                "set_position": "mid",
                "flows_from": ["minimal", "detroit", "progressive"],
                "flows_into": ["driving", "peak_time", "tribal"],
            },
            {
                "name": "driving",
                "artists": ["Chris Liebing", "Speedy J", "Adam Beyer", "Alignment"],
                "labels": ["CLR", "Tresor", "Drumcode"],
                "set_position": "mid-to-peak",
                "flows_from": ["progressive", "hypnotic"],
                "flows_into": ["peak_time", "tribal", "industrial"],
            },
            {
                "name": "tribal",
                "artists": ["Luciano", "Zip", "Sleepy & Boo", "Cio D'Or"],
                "labels": ["Cadenza", "Perlon"],
                "set_position": "mid",
                "flows_from": ["driving", "hypnotic"],
                "flows_into": ["breakbeat", "peak_time"],
            },
            {
                "name": "breakbeat",
                "artists": ["Surgeon", "Blawan", "Truss", "Shifted"],
                "labels": ["Mote-Evolver", "Avian"],
                "set_position": "peak",
                "flows_from": ["tribal", "driving"],
                "flows_into": ["peak_time", "acid"],
            },
            {
                "name": "peak_time",
                "artists": ["Adam Beyer", "Amelie Lens", "Charlotte de Witte", "SPFDJ"],
                "labels": ["Drumcode", "EXHALE", "Turbo"],
                "set_position": "peak",
                "flows_from": ["driving", "detroit", "hypnotic"],
                "flows_into": ["industrial", "hard_techno", "acid"],
            },
            {
                "name": "acid",
                "artists": ["DJ Pierre", "Hardfloor", "I-f", "Luke Slater"],
                "labels": ["Djax-Up-Beats", "Intec"],
                "set_position": "peak",
                "flows_from": ["detroit", "peak_time", "breakbeat"],
                "flows_into": ["industrial", "hard_techno"],
            },
            {
                "name": "raw",
                "artists": ["Paula Temple", "Phase", "Rebekah", "Ancient Methods"],
                "labels": ["Noise Manifesto", "Enemy Records"],
                "set_position": "peak-to-closing",
                "flows_from": ["industrial", "peak_time"],
                "flows_into": ["hard_techno", "industrial"],
            },
            {
                "name": "industrial",
                "artists": ["Ancient Methods", "Orphx", "Surgeon", "Paula Temple"],
                "labels": ["M-Plant", "Sonic Groove", "Tresor"],
                "set_position": "peak",
                "flows_from": ["detroit", "peak_time", "driving"],
                "flows_into": ["hard_techno", "raw"],
            },
            {
                "name": "hard_techno",
                "artists": ["SPFDJ", "Alignment", "Sara Landry", "Reinier Zonneveld"],
                "labels": ["Alignment", "Turbo"],
                "set_position": "peak",
                "flows_from": ["industrial", "raw", "peak_time"],
                "flows_into": [],
            },
        ],
    }
    return json.dumps(data, indent=2)

@resource(
    uri="knowledge://set-dynamics",
    name="Set Dynamics",
    title="DJ Set Construction Theory",
    description=(
        "Theory of how to build a DJ set: the 20-minute rule, energy arc shape, "
        "tension-release cycles, hard transition rules, and phrase awareness. "
        "Use this to make structural decisions without asking the user."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
)
async def set_dynamics() -> str:
    """Get DJ set construction theory."""
    data = {
        "twenty_minute_rule": {
            "rule": (
                "Crowds need 20 minutes to warm up. Opening with peak energy empties "
                "the dancefloor. Start below the target energy level and build."
            ),
            "implication": (
                "First 20 minutes: LUFS < -13, BPM at lower end of target range, "
                "minimal subgenres preferred."
            ),
        },
        "energy_arc": {
            "shape": "Build to ~70% through the set, then slight resolution",
            "ideal_lufs_start": -13.0,
            "ideal_lufs_peak": -10.0,
            "ideal_lufs_end": -11.0,
            "peak_position": "70% into the set",
            "rule": (
                "A set tells a story — tension builds, peaks, then resolves. "
                "Without resolution, the crowd feels exhausted, not satisfied."
            ),
        },
        "tension_release_cycles": {
            "interval_minutes": "20-30",
            "rule": (
                "Every 20–30 minutes, introduce a breakdown or softer track. "
                "This resets attention and makes the next peak hit harder."
            ),
            "implementation": (
                "Drop 1-2 energy levels (e.g., peak_time → driving) for one track, "
                "then build back up."
            ),
        },
        "hard_rules": [
            "Never jump more than 2 energy levels between consecutive tracks",
            "Outro should land (resolve), not cliff-drop",
            "BPM shifts > 8 BPM in one step require a transition track",
            "Camelot distance ≥ 5 is audibly dissonant — avoid unless intentional",
        ],
        "phrase_awareness": {
            "rule": (
                "Techno tracks operate in 8- and 16-bar phrases. "
                "Transitions work best at phrase boundaries (every 32 beats at 130 BPM ≈ 14.8 seconds)."
            ),
            "tip": (
                "Outro lengths in the library indicate mix-in points. "
                "Use tracks with long outros for smooth blends."
            ),
        },
    }
    return json.dumps(data, indent=2)

@resource(
    uri="knowledge://dancefloor-psychology",
    name="Dancefloor Psychology",
    title="Dancefloor Psychology",
    description=(
        "How crowds respond to music and why. Maps crowd states to audio signatures "
        "and explains when/why to use atmospheric, hypnotic, or hard tracks."
    ),
    mime_type="application/json",
    tags={"knowledge"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_REFERENCE,
    meta=RESOURCE_META,
)
async def dancefloor_psychology() -> str:
    """Get dancefloor crowd psychology reference."""
    data = {
        "crowd_states": [
            {
                "state": "hands_in_the_air",
                "description": "Euphoric peak moment",
                "audio_signatures": [
                    "bright lead synths",
                    "euphoric harmonic progressions",
                    "loud kick",
                    "LUFS -9 to -8",
                ],
                "typical_subgenres": ["peak_time", "hard_techno"],
            },
            {
                "state": "nodding_heads",
                "description": "Deep hypnotic lock-in",
                "audio_signatures": [
                    "hypnotic loops",
                    "minimal variation",
                    "consistent groove",
                    "LUFS -12 to -11",
                ],
                "typical_subgenres": ["hypnotic", "minimal", "driving"],
            },
            {
                "state": "eyes_closed_arms_crossed",
                "description": "Serious dancefloor — dark atmosphere",
                "audio_signatures": [
                    "dark atmosphere",
                    "low melodic content",
                    "industrial textures",
                    "LUFS -11 to -10",
                ],
                "typical_subgenres": ["industrial", "detroit", "raw"],
            },
        ],
        "energy_recovery": {
            "rule": (
                "After an intense peak, one softer track lets the crowd catch breath "
                "without losing them. Skip it and they leave."
            ),
            "signature": "1-2 LUFS softer than preceding track, same BPM range",
            "duration": "One track (5-8 minutes) is enough",
        },
        "harmonic_mixing_perception": {
            "rule": (
                "Out-of-key transitions sound 'wrong' even to non-musicians. "
                "Camelot distance ≥ 5 is audible on a good system."
            ),
            "safe_distances": [0, 1],
            "tension_distance": [2, 3],
            "avoid_distance": "≥ 5",
            "tip": (
                "Energy boost: move one position clockwise on the Camelot wheel "
                "(e.g., 8A → 9A). Creates forward momentum."
            ),
        },
    }
    return json.dumps(data, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_resources/test_knowledge.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 5: Check types**

```bash
uv run mypy app/controllers/resources/knowledge.py
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/resources/knowledge.py tests/test_resources/test_knowledge.py
git commit -m "feat: add knowledge:// static resources for DJ expert session"
```

---

## Task 2: Library Snapshot Resource

**Files:**
- Create: `app/controllers/resources/snapshot.py`
- Test: `tests/test_resources/test_snapshot.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resources/test_snapshot.py
"""Tests for library://snapshot aggregation resource."""
from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_snapshot_empty_db(db: AsyncSession):
    """Snapshot on empty DB returns valid structure with zero counts."""
    from unittest.mock import patch

    from app.controllers.resources.snapshot import library_snapshot

    result = await library_snapshot(session=db)
    data = json.loads(result)

    assert "total_tracks" in data
    assert "tracks_with_features" in data
    assert "mood_distribution" in data
    assert "playlists" in data
    assert "last_analyzed" in data
    assert data["total_tracks"] == 0
    assert data["mood_distribution"] == {}

@pytest.mark.asyncio
async def test_snapshot_with_tracks(db: AsyncSession, async_engine):
    """Snapshot returns correct mood distribution when tracks exist."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.controllers.resources.snapshot import library_snapshot
    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Detroit Track")
        t2 = Track(title="Industrial Track")
        t3 = Track(title="No Mood Track")
        session.add_all([t1, t2, t3])
        await session.flush()
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t1.id, bpm=132.0, mood="detroit", integrated_lufs=-11.5
            )
        )
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t2.id, bpm=140.0, mood="industrial", integrated_lufs=-10.0
            )
        )
        await session.commit()

    result = await library_snapshot(session=db)
    data = json.loads(result)
    assert data["total_tracks"] == 3
    assert data["tracks_with_features"] == 2
    assert data["mood_distribution"].get("detroit", 0) == 1
    assert data["mood_distribution"].get("industrial", 0) == 1

@pytest.mark.asyncio
async def test_snapshot_playlists(db: AsyncSession, async_engine):
    """Snapshot includes playlist list with track counts."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.controllers.resources.snapshot import library_snapshot
    from app.db.models.playlist import Playlist, PlaylistItem
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        pl = Playlist(name="Dark Rollers")
        session.add(pl)
        await session.flush()
        t = Track(title="Test")
        session.add(t)
        await session.flush()
        session.add(PlaylistItem(playlist_id=pl.id, track_id=t.id, position=0))
        await session.commit()

    result = await library_snapshot(session=db)
    data = json.loads(result)
    assert len(data["playlists"]) == 1
    assert data["playlists"][0]["name"] == "Dark Rollers"
    assert data["playlists"][0]["track_count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_resources/test_snapshot.py -v
```
Expected: `ImportError: cannot import name 'library_snapshot' from 'app.controllers.resources.snapshot'`

- [ ] **Step 3: Implement the snapshot resource**

Create `app/controllers/resources/snapshot.py`:

```python
"""Snapshot resource — single-call library context for AI session initialization.

Resources:
- library://snapshot — track counts by mood, playlists, last-analyzed timestamp
"""

from __future__ import annotations

import json

from fastmcp.dependencies import Depends
from fastmcp.resources import resource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
)
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.track import Track

@resource(
    uri="library://snapshot",
    name="Library Snapshot",
    title="Library Snapshot",
    description=(
        "Single-call library context for AI session initialization. "
        "Returns track counts by subgenre/mood, playlist list with track counts, "
        "and the last-analyzed timestamp. Read this once at session start."
    ),
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
)
async def library_snapshot(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> str:
    """Get library snapshot for AI session initialization.

    Returns JSON with:
    - total_tracks: int
    - tracks_with_features: int
    - mood_distribution: dict[str, int] — count per subgenre/mood
    - playlists: list of {id, name, track_count}
    - last_analyzed: ISO timestamp or null
    """
    total_result = await session.execute(select(func.count(Track.id)))
    total_tracks = total_result.scalar() or 0

    features_result = await session.execute(
        select(func.count(TrackAudioFeaturesComputed.track_id))
    )
    tracks_with_features = features_result.scalar() or 0

    # Mood distribution: group by mood, skip nulls
    mood_rows = await session.execute(
        select(TrackAudioFeaturesComputed.mood, func.count())
        .where(TrackAudioFeaturesComputed.mood.isnot(None))
        .group_by(TrackAudioFeaturesComputed.mood)
        .order_by(func.count().desc())
    )
    mood_distribution = {row[0]: row[1] for row in mood_rows}

    # Last analyzed: max updated_at on features table
    last_analyzed_result = await session.execute(
        select(func.max(TrackAudioFeaturesComputed.updated_at))
    )
    last_analyzed_raw = last_analyzed_result.scalar()
    last_analyzed = last_analyzed_raw.isoformat() if last_analyzed_raw else None

    # Playlists with track counts
    playlist_rows = await session.execute(
        select(
            Playlist.id,
            Playlist.name,
            func.count(PlaylistItem.track_id).label("track_count"),
        )
        .outerjoin(PlaylistItem, PlaylistItem.playlist_id == Playlist.id)
        .group_by(Playlist.id, Playlist.name)
        .order_by(Playlist.name)
    )
    playlists = [
        {"id": row.id, "name": row.name, "track_count": row.track_count}
        for row in playlist_rows
    ]

    data = {
        "total_tracks": total_tracks,
        "tracks_with_features": tracks_with_features,
        "feature_coverage_pct": (
            round(tracks_with_features / total_tracks * 100, 1) if total_tracks else 0.0
        ),
        "mood_distribution": mood_distribution,
        "playlists": playlists,
        "last_analyzed": last_analyzed,
    }
    return json.dumps(data, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_resources/test_snapshot.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Check types**

```bash
uv run mypy app/controllers/resources/snapshot.py
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/resources/snapshot.py tests/test_resources/test_snapshot.py
git commit -m "feat: add library://snapshot aggregation resource"
```

---

## Task 3: DJ Expert Session Prompt

**Files:**
- Create: `app/controllers/prompts/workflows/dj_expert_session.py`
- Test: `tests/test_prompts/test_dj_expert_session.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompts/test_dj_expert_session.py
"""Tests for dj_expert_session prompt structure."""
from __future__ import annotations

import pytest

@pytest.mark.asyncio
async def test_prompt_returns_two_messages():
    """dj_expert_session returns a user + assistant message pair."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    messages = dj_expert_session()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"

@pytest.mark.asyncio
async def test_prompt_references_all_knowledge_resources():
    """User message instructs reading all 4 knowledge:// and library://snapshot."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    messages = dj_expert_session()
    user_content = messages[0].content

    required_resources = [
        "knowledge://vocabulary",
        "knowledge://subgenre-culture",
        "knowledge://set-dynamics",
        "knowledge://dancefloor-psychology",
        "library://snapshot",
    ]
    for res in required_resources:
        assert res in user_content, f"Prompt missing resource reference: {res}"

@pytest.mark.asyncio
async def test_prompt_with_goal():
    """Passing goal embeds it in the user message."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    messages = dj_expert_session(goal="dark and driving, 90 minutes, after midnight")
    assert "dark and driving" in messages[0].content
    assert "90 minutes" in messages[0].content

@pytest.mark.asyncio
async def test_assistant_message_is_dj_style():
    """Assistant message demonstrates DJ-style response, not database-style."""
    from app.controllers.prompts.workflows.dj_expert_session import dj_expert_session

    messages = dj_expert_session()
    assistant_content = messages[1].content
    # Should mention proactive action, not form-filling
    assert len(assistant_content) > 50
    # Must not contain database jargon in the opening
    assert "SELECT" not in assistant_content
    assert "query" not in assistant_content.lower() or "one question" in assistant_content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_prompts/test_dj_expert_session.py -v
```
Expected: `ImportError: cannot import name 'dj_expert_session' from 'app.controllers.prompts.workflows.dj_expert_session'`

- [ ] **Step 3: Implement the prompt**

Create `app/controllers/prompts/workflows/dj_expert_session.py`:

```python
"""DJ Expert Session initialization prompt.

Boots the AI as an experienced DJ: reads all knowledge and library
resources, then issues behavioral instructions and an opening message.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp.prompts import Message, prompt
from pydantic import Field

@prompt(
    name="dj_expert_session",
    title="DJ Expert Session",
    description=(
        "Initialize a DJ expert session. The AI reads all knowledge resources, "
        "learns the library state, and then operates as a professional DJ — "
        "translating natural language intent into optimized sets without asking "
        "for technical parameters."
    ),
    tags={"knowledge", "workflow"},
    meta={"version": "1.0"},
)
def dj_expert_session(
    goal: Annotated[
        str | None,
        Field(description="Optional session goal (e.g. 'dark and driving, 90 min, after midnight')"),
    ] = None,
) -> list[Message]:
    """Initialize the AI as a professional DJ expert.

    Steps performed:
    1. Read library://snapshot for current library state
    2. Read reference://subgenres, reference://camelot, reference://templates
    3. Read all 4 knowledge:// resources
    4. Issue behavioral instructions
    5. Return an opening message in DJ assistant style

    Args:
        goal: Optional user intent to anchor the opening message.
    """
    goal_line = f"\n\nUser's goal for this session: **{goal}**" if goal else ""

    user_message = f"""You are initializing as a professional DJ expert assistant. 
Complete the following setup steps before responding to the user:

**Step 1 — Read library state:**
- `library://snapshot` — track counts by subgenre, playlists, last-analyzed

**Step 2 — Read domain references:**
- `reference://subgenres` — all 15 techno subgenres with energy levels and BPM ranges
- `reference://camelot` — Camelot wheel compatibility rules
- `reference://templates` — 8 set templates with slot definitions and energy arcs

**Step 3 — Read knowledge resources:**
- `knowledge://vocabulary` — map human descriptors (dark, driving, hypnotic) to subgenres/BPM/features
- `knowledge://subgenre-culture` — artists, set position, transition neighbors per subgenre
- `knowledge://set-dynamics` — 20-minute rule, energy arc theory, tension-release cycles
- `knowledge://dancefloor-psychology` — crowd states, energy recovery, harmonic mixing perception

**Step 4 — Adopt these behavioral rules:**
- Translate human intent using `knowledge://vocabulary`. Never ask "what BPM range?"
- Make reasonable assumptions and state them briefly (one sentence max)
- Ask questions only when intent is genuinely ambiguous — at most one question
- Speak like a DJ, not a database interface. "I'll pull dark Detroit and industrial, 132–140 BPM" not "I will query tracks where mood IN ('detroit', 'industrial')"
- When the library has few tracks for a subgenre, say so and suggest alternatives
- Use `get_candidate_pool` to explore before committing to `build_set`
- Use `preview_set_arc` to evaluate orderings before saving{goal_line}

After completing setup, greet the user as a DJ assistant ready to work."""

    if goal:
        # Build an opinionated opening message specific to the stated goal
        assistant_message = (
            f"I've loaded the library and knowledge base. "
            f"I can see you're after: **{goal}**. "
            f"Let me pull candidate tracks and sketch a set arc — "
            f"I'll use `get_candidate_pool` to sample the pool, then `preview_set_arc` "
            f"to check the flow before building. One question if needed, otherwise I'll proceed."
        )
    else:
        assistant_message = (
            "Library loaded. I know the subgenres, Camelot wheel, templates, "
            "and dancefloor psychology. Tell me what you need — "
            "a mood, a time slot, a duration — and I'll build it. "
            "I won't ask you for BPM ranges."
        )

    return [
        Message(user_message, role="user"),
        Message(assistant_message, role="assistant"),
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_prompts/test_dj_expert_session.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 5: Check types**

```bash
uv run mypy app/controllers/prompts/workflows/dj_expert_session.py
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/prompts/workflows/dj_expert_session.py \
        tests/test_prompts/test_dj_expert_session.py
git commit -m "feat: add dj_expert_session initialization prompt"
```

---

## Task 4: Pure Preview Logic

**Files:**
- Create: `app/optimization/preview.py`
- Test: `tests/test_optimization/test_preview.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_optimization/test_preview.py
"""Tests for preview_arc pure function."""
from __future__ import annotations

import pytest

from app.entities.audio.features import TrackFeatures
from app.optimization.preview import PreviewResult, preview_arc
from app.transition.scorer import TransitionScorer

def _make_features(bpm: float, lufs: float, key_code: int = 0) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, integrated_lufs=lufs, key_code=key_code)

def _make_scorer() -> TransitionScorer:
    return TransitionScorer()

def test_preview_arc_returns_correct_structure():
    """preview_arc returns PreviewResult with all required fields."""
    scorer = _make_scorer()
    features_map = {
        1: _make_features(132.0, -11.5),
        2: _make_features(133.0, -11.0),
        3: _make_features(134.0, -10.5),
    }
    result = preview_arc(scorer, features_map, track_ids=[1, 2, 3])

    assert isinstance(result, PreviewResult)
    assert 0.0 <= result.score <= 1.0
    assert len(result.energy_arc) == 3
    assert len(result.bpm_arc) == 3
    assert isinstance(result.weak_spots, list)
    assert isinstance(result.recommendation, str)
    assert len(result.recommendation) > 0

def test_preview_arc_energy_arc_matches_lufs():
    """energy_arc values correspond to track LUFS values."""
    scorer = _make_scorer()
    lufs_values = [-13.0, -12.0, -11.0, -10.0]
    features_map = {i: _make_features(132.0, lufs) for i, lufs in enumerate(lufs_values)}
    result = preview_arc(scorer, features_map, track_ids=list(range(4)))

    assert result.energy_arc == lufs_values

def test_preview_arc_bpm_arc_matches_bpm():
    """bpm_arc values correspond to track BPM values."""
    scorer = _make_scorer()
    bpm_values = [130.0, 132.0, 134.0, 136.0]
    features_map = {i: _make_features(bpm, -11.0) for i, bpm in enumerate(bpm_values)}
    result = preview_arc(scorer, features_map, track_ids=list(range(4)))

    assert result.bpm_arc == bpm_values

def test_preview_arc_weak_spots_are_valid_positions():
    """weak_spots contains positions 0..n-2 (transition positions)."""
    scorer = _make_scorer()
    # Create a deliberately bad transition: big BPM jump
    features_map = {
        0: _make_features(120.0, -13.0, key_code=0),
        1: _make_features(150.0, -8.0, key_code=12),  # huge BPM + key jump
        2: _make_features(122.0, -13.0, key_code=0),
    }
    result = preview_arc(scorer, features_map, track_ids=[0, 1, 2])

    for pos in result.weak_spots:
        assert 0 <= pos < 2, f"weak_spot {pos} out of range for 3-track set"

def test_preview_arc_missing_features_skipped():
    """Tracks missing from features_map are excluded gracefully."""
    scorer = _make_scorer()
    features_map = {
        1: _make_features(132.0, -11.5),
        # track_id=2 intentionally missing
        3: _make_features(134.0, -10.5),
    }
    result = preview_arc(scorer, features_map, track_ids=[1, 2, 3])
    # Should return result for the 2 tracks that have features
    assert len(result.energy_arc) == 2
    assert len(result.bpm_arc) == 2

def test_preview_arc_single_track():
    """Single track returns score 1.0 (no transitions to score)."""
    scorer = _make_scorer()
    features_map = {1: _make_features(132.0, -11.5)}
    result = preview_arc(scorer, features_map, track_ids=[1])

    assert result.score == 1.0
    assert result.weak_spots == []

def test_preview_arc_recommendation_mentions_score():
    """Recommendation string mentions the score or quality level."""
    scorer = _make_scorer()
    features_map = {i: _make_features(132.0 + i, -11.0) for i in range(5)}
    result = preview_arc(scorer, features_map, track_ids=list(range(5)))

    # Recommendation should contain numerical or qualitative score mention
    assert any(
        word in result.recommendation.lower()
        for word in ["score", "quality", "good", "weak", "strong", "transition"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_optimization/test_preview.py -v
```
Expected: `ImportError: cannot import name 'preview_arc' from 'app.optimization.preview'`

- [ ] **Step 3: Implement pure preview logic**

Create `app/optimization/preview.py`:

```python
"""Pure preview logic for set arc evaluation.

No I/O, no DB, no async. Given a dict of TrackFeatures and an ordered
list of track IDs, computes fitness, per-position arcs, and identifies
weak transition spots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import compute_fitness
from app.templates.models import SetTemplateDefinition
from app.transition.scorer import TransitionScorer

_WEAK_SPOT_THRESHOLD = 0.45

@dataclass
class PreviewResult:
    """Result of a non-destructive set arc preview."""

    score: float
    energy_arc: list[float]
    bpm_arc: list[float]
    weak_spots: list[int]
    recommendation: str
    missing_track_ids: list[int] = field(default_factory=list)

def preview_arc(
    scorer: TransitionScorer,
    features_map: dict[int, TrackFeatures],
    track_ids: list[int],
    template: SetTemplateDefinition | None = None,
    moods: dict[int, str | None] | None = None,
) -> PreviewResult:
    """Evaluate a specific track ordering without saving anything.

    Args:
        scorer: Initialized TransitionScorer (no weights override needed for preview).
        features_map: Mapping of track_id → TrackFeatures.
        track_ids: Ordered list of track IDs to evaluate.
        template: Optional template definition for template_fitness scoring.
        moods: Optional external mood overrides keyed by track_id.

    Returns:
        PreviewResult with fitness score, arcs, weak spots, and recommendation.
    """
    # Filter to only tracks that have features; note missing ones
    valid_ids = [tid for tid in track_ids if tid in features_map]
    missing = [tid for tid in track_ids if tid not in features_map]

    if len(valid_ids) <= 1:
        return PreviewResult(
            score=1.0,
            energy_arc=[features_map[valid_ids[0]].integrated_lufs or 0.0] if valid_ids else [],
            bpm_arc=[features_map[valid_ids[0]].bpm or 0.0] if valid_ids else [],
            weak_spots=[],
            recommendation="Only one track — no transitions to evaluate.",
            missing_track_ids=missing,
        )

    tracks = [features_map[tid] for tid in valid_ids]
    # order and idx_map use positional indices matching how compute_fitness expects them
    order = list(range(len(valid_ids)))
    idx_map = {i: i for i in range(len(valid_ids))}
    # Remap moods to positional indices if provided
    positional_moods: dict[int, str | None] | None = None
    if moods:
        positional_moods = {
            i: moods.get(tid) for i, tid in enumerate(valid_ids)
        }

    score = compute_fitness(scorer, tracks, order, idx_map, template=template, moods=positional_moods)

    energy_arc = [t.integrated_lufs if t.integrated_lufs is not None else 0.0 for t in tracks]
    bpm_arc = [t.bpm if t.bpm is not None else 0.0 for t in tracks]

    weak_spots = _find_weak_spots(scorer, tracks)

    recommendation = _build_recommendation(score, weak_spots, missing, len(valid_ids))

    return PreviewResult(
        score=round(score, 3),
        energy_arc=energy_arc,
        bpm_arc=bpm_arc,
        weak_spots=weak_spots,
        recommendation=recommendation,
        missing_track_ids=missing,
    )

def _find_weak_spots(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
) -> list[int]:
    """Return 0-based positions (of the outgoing track) where transition score < threshold."""
    weak: list[int] = []
    for i in range(len(tracks) - 1):
        result = scorer.score(tracks[i], tracks[i + 1])
        transition_score = 0.01 if result.hard_reject else result.overall
        if transition_score < _WEAK_SPOT_THRESHOLD:
            weak.append(i)
    return weak

def _build_recommendation(
    score: float,
    weak_spots: list[int],
    missing: list[int],
    n_tracks: int,
) -> str:
    """Build a plain-language recommendation string."""
    parts: list[str] = []

    if score >= 0.75:
        parts.append(f"Strong set arc (score {score:.2f}).")
    elif score >= 0.55:
        parts.append(f"Decent arc (score {score:.2f}) — room for improvement.")
    else:
        parts.append(f"Weak arc (score {score:.2f}) — significant transition problems.")

    if weak_spots:
        positions = ", ".join(str(p + 1) for p in weak_spots)
        parts.append(
            f"Weak transition{'s' if len(weak_spots) > 1 else ''} after "
            f"position{'s' if len(weak_spots) > 1 else ''} {positions}."
        )
    else:
        parts.append("All transitions within acceptable range.")

    if missing:
        parts.append(
            f"{len(missing)} track{'s' if len(missing) > 1 else ''} "
            f"had no features and were excluded."
        )

    return " ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_optimization/test_preview.py -v
```
Expected: All 7 tests PASS.

- [ ] **Step 5: Check types and architecture**

```bash
uv run mypy app/optimization/preview.py
uv run lint-imports
```
Expected: no errors. `app/optimization/preview.py` is pure — it only imports from `app.entities`, `app.optimization.fitness`, `app.templates.models`, `app.transition.scorer`.

- [ ] **Step 6: Commit**

```bash
git add app/optimization/preview.py tests/test_optimization/test_preview.py
git commit -m "feat: add pure preview_arc() for non-destructive set evaluation"
```

---

## Task 5: `get_candidate_pool` Tool

**Files:**
- Create: `app/controllers/tools/candidate_pool.py`
- Test: `tests/test_tools/test_candidate_pool.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools/test_candidate_pool.py
"""Integration tests for get_candidate_pool and preview_set_arc tools."""
from __future__ import annotations

import json

import pytest
from fastmcp import Client
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import _parse_tool_result as _parse

@pytest.mark.asyncio
async def test_candidate_pool_empty_returns_empty_list(client: Client):
    """get_candidate_pool on empty DB returns empty list."""
    result = await client.call_tool("get_candidate_pool", {})
    data = _parse(result)
    assert data["tracks"] == []
    assert data["total"] == 0

@pytest.mark.asyncio
async def test_candidate_pool_filters_by_subgenre(client: Client, async_engine):
    """get_candidate_pool filters by subgenre (mood field)."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        t1 = Track(title="Detroit Track")
        t2 = Track(title="Industrial Track")
        t3 = Track(title="Minimal Track")
        session.add_all([t1, t2, t3])
        await session.flush()
        session.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=132.0, mood="detroit", integrated_lufs=-11.5))
        session.add(TrackAudioFeaturesComputed(track_id=t2.id, bpm=140.0, mood="industrial", integrated_lufs=-10.0))
        session.add(TrackAudioFeaturesComputed(track_id=t3.id, bpm=128.0, mood="minimal", integrated_lufs=-12.5))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"subgenres": ["detroit", "industrial"]})
    data = _parse(result)
    assert data["total"] == 2
    moods = {t["mood"] for t in data["tracks"]}
    assert "detroit" in moods
    assert "industrial" in moods
    assert "minimal" not in moods

@pytest.mark.asyncio
async def test_candidate_pool_filters_by_bpm(client: Client, async_engine):
    """get_candidate_pool filters by BPM range."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for i, bpm in enumerate([126.0, 132.0, 138.0, 145.0]):
            t = Track(title=f"Track {i}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=bpm, integrated_lufs=-11.0))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"bpm_min": 130.0, "bpm_max": 140.0})
    data = _parse(result)
    assert data["total"] == 2
    for t in data["tracks"]:
        assert 130.0 <= t["bpm"] <= 140.0

@pytest.mark.asyncio
async def test_candidate_pool_energy_level_high(client: Client, async_engine):
    """energy_level='high' filters by LUFS >= -11."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for lufs in [-14.0, -12.0, -10.5, -9.0]:
            t = Track(title=f"Track {lufs}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=132.0, integrated_lufs=lufs))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"energy_level": "high"})
    data = _parse(result)
    assert data["total"] == 2
    for t in data["tracks"]:
        assert t["energy_lufs"] >= -11.0

@pytest.mark.asyncio
async def test_candidate_pool_respects_limit(client: Client, async_engine):
    """get_candidate_pool respects the limit parameter."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for i in range(20):
            t = Track(title=f"Track {i}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=132.0, integrated_lufs=-11.0))
        await session.commit()

    result = await client.call_tool("get_candidate_pool", {"limit": 5})
    data = _parse(result)
    assert len(data["tracks"]) == 5
    assert data["total"] == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tools/test_candidate_pool.py::test_candidate_pool_empty_returns_empty_list -v
```
Expected: `fastmcp.exceptions.ToolError: Unknown tool: get_candidate_pool`

- [ ] **Step 3: Implement the candidate pool tool**

Create `app/controllers/tools/candidate_pool.py`:

```python
"""Candidate pool exploration tool.

Tools:
- get_candidate_pool — explore the library before committing to build_set
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ICON_TRACKS,
    TOOL_META,
    ToolCategory,
)
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track

_ENERGY_LEVEL_LUFS: dict[str, tuple[float | None, float | None]] = {
    "low": (None, -13.0),
    "mid": (-13.0, -11.0),
    "high": (-11.0, None),
}

@tool(
    title="Get Candidate Pool",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
async def get_candidate_pool(
    description: Annotated[
        str | None,
        Field(description="Natural language description (e.g. 'dark hypnotic tracks'). Informational — use other params for filtering."),
    ] = None,
    subgenres: Annotated[
        list[str] | None,
        Field(description="Filter by subgenre/mood (e.g. ['detroit', 'industrial'])"),
    ] = None,
    bpm_min: Annotated[float | None, Field(description="Minimum BPM")] = None,
    bpm_max: Annotated[float | None, Field(description="Maximum BPM")] = None,
    energy_level: Annotated[
        Literal["low", "mid", "high"] | None,
        Field(description="Energy tier: low (LUFS < -13), mid (-13 to -11), high (> -11)"),
    ] = None,
    lufs_min: Annotated[float | None, Field(description="Minimum integrated LUFS (overrides energy_level lower bound)")] = None,
    lufs_max: Annotated[float | None, Field(description="Maximum integrated LUFS (overrides energy_level upper bound)")] = None,
    limit: Annotated[int, Field(description="Max tracks to return", ge=1, le=200)] = 50,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Explore library tracks matching criteria without creating a set.

    Use this before build_set to: verify enough tracks exist for a subgenre,
    sample the candidate pool by BPM/energy, or check track quality distribution.
    Does not write anything to the database.
    """
    stmt = (
        select(Track, TrackAudioFeaturesComputed)
        .join(TrackAudioFeaturesComputed, TrackAudioFeaturesComputed.track_id == Track.id)
        .where(Track.status == 0)
    )

    if subgenres:
        stmt = stmt.where(TrackAudioFeaturesComputed.mood.in_(subgenres))

    if bpm_min is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
    if bpm_max is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)

    # LUFS bounds: explicit params override energy_level tier
    effective_lufs_min = lufs_min
    effective_lufs_max = lufs_max
    if energy_level is not None and effective_lufs_min is None and effective_lufs_max is None:
        tier_min, tier_max = _ENERGY_LEVEL_LUFS[energy_level]
        effective_lufs_min = tier_min
        effective_lufs_max = tier_max

    if effective_lufs_min is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.integrated_lufs >= effective_lufs_min)
    if effective_lufs_max is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.integrated_lufs <= effective_lufs_max)

    # Count total before limit
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(TrackAudioFeaturesComputed.bpm).limit(limit)
    rows = (await session.execute(stmt)).all()

    tracks = [
        {
            "id": track.id,
            "title": track.title,
            "bpm": features.bpm,
            "mood": features.mood,
            "energy_lufs": features.integrated_lufs,
            "key_code": features.key_code,
        }
        for track, features in rows
    ]

    return {
        "tracks": tracks,
        "total": total,
        "returned": len(tracks),
        "filters_applied": {
            "description": description,
            "subgenres": subgenres,
            "bpm_min": bpm_min,
            "bpm_max": bpm_max,
            "energy_level": energy_level,
            "lufs_min": effective_lufs_min,
            "lufs_max": effective_lufs_max,
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_candidate_pool.py -k "candidate_pool" -v
```
Expected: All 5 `test_candidate_pool_*` tests PASS.

- [ ] **Step 5: Check types**

```bash
uv run mypy app/controllers/tools/candidate_pool.py
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/controllers/tools/candidate_pool.py tests/test_tools/test_candidate_pool.py
git commit -m "feat: add get_candidate_pool read-only exploration tool"
```

---

## Task 6: `preview_set_arc` Tool

**Files:**
- Modify: `app/controllers/tools/sets.py` (add tool at end of file)
- Test: `tests/test_tools/test_candidate_pool.py` (add tests to existing file)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_tools/test_candidate_pool.py`)

```python
# Append to tests/test_tools/test_candidate_pool.py

@pytest.mark.asyncio
async def test_preview_set_arc_empty_ids(client: Client):
    """preview_set_arc with empty track_ids returns score 1.0."""
    result = await client.call_tool("preview_set_arc", {"track_ids": []})
    data = _parse(result)
    assert data["score"] == 1.0
    assert data["energy_arc"] == []
    assert data["bpm_arc"] == []
    assert data["weak_spots"] == []

@pytest.mark.asyncio
async def test_preview_set_arc_with_tracks(client: Client, async_engine):
    """preview_set_arc returns arc data for tracks with features."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    track_ids = []
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        for i, (bpm, lufs) in enumerate([(130.0, -13.0), (132.0, -12.0), (134.0, -11.0)]):
            t = Track(title=f"Track {i}")
            session.add(t)
            await session.flush()
            session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=bpm, integrated_lufs=lufs, key_code=0))
            track_ids.append(t.id)
        await session.commit()

    result = await client.call_tool("preview_set_arc", {"track_ids": track_ids})
    data = _parse(result)

    assert 0.0 <= data["score"] <= 1.0
    assert len(data["energy_arc"]) == 3
    assert len(data["bpm_arc"]) == 3
    assert data["energy_arc"] == [-13.0, -12.0, -11.0]
    assert data["bpm_arc"] == [130.0, 132.0, 134.0]
    assert isinstance(data["recommendation"], str)
    assert len(data["recommendation"]) > 0

@pytest.mark.asyncio
async def test_preview_set_arc_missing_tracks_noted(client: Client, async_engine):
    """preview_set_arc notes track IDs that have no features."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        from app.db.models.audio import TrackAudioFeaturesComputed
        from app.db.models.track import Track

        t = Track(title="Has Features")
        session.add(t)
        await session.flush()
        session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=132.0, integrated_lufs=-11.5))
        real_id = t.id
        await session.commit()

    result = await client.call_tool("preview_set_arc", {"track_ids": [real_id, 99999]})
    data = _parse(result)
    assert 99999 in data["missing_track_ids"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tools/test_candidate_pool.py::test_preview_set_arc_empty_ids -v
```
Expected: `fastmcp.exceptions.ToolError: Unknown tool: preview_set_arc`

- [ ] **Step 3: Add preview_set_arc to sets.py**

Read the current end of `app/controllers/tools/sets.py` (after the `get_set_templates` function), then append:

```python
# Add these imports at the top of app/controllers/tools/sets.py
from app.controllers.dependencies import get_feature_repo
from app.db.repositories.feature import FeatureRepository
from app.optimization.preview import preview_arc
from app.transition.scorer import TransitionScorer
```

Add at the end of `app/controllers/tools/sets.py`:

```python
@tool(
    title="Preview Set Arc",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def preview_set_arc(
    track_ids: Annotated[list[int], Field(description="Ordered list of track IDs to evaluate")],
    template: Annotated[
        str | None,
        Field(description="Optional template name (e.g. 'roller_90') for template fitness scoring"),
    ] = None,
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> dict[str, Any]:
    """Evaluate a track ordering's fitness without saving a set version.

    Runs the same fitness function used by build_set, but non-destructively.
    Use before committing to an ordering — compare multiple arc shapes and
    identify weak transitions before calling build_set or rebuild_set.

    Returns score (0-1), energy/BPM arcs, weak spot positions, and a
    plain-language recommendation.
    """
    if not track_ids:
        from app.optimization.preview import PreviewResult
        result = PreviewResult(
            score=1.0, energy_arc=[], bpm_arc=[], weak_spots=[],
            recommendation="No tracks provided.", missing_track_ids=[],
        )
    else:
        features_map = await feat_repo.get_scoring_features_batch(track_ids)
        scorer = TransitionScorer()

        template_def = None
        if template is not None:
            template_def = TEMPLATES.get(template)

        result = preview_arc(scorer, features_map, track_ids, template=template_def)

    from dataclasses import asdict
    return asdict(result)
```

The full import additions to the top of `sets.py` (add after the existing imports):

```python
from app.controllers.dependencies import get_feature_repo
from app.db.repositories.feature import FeatureRepository
from app.optimization.preview import PreviewResult, preview_arc
from app.transition.scorer import TransitionScorer
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_tools/test_candidate_pool.py -k "preview_set_arc" -v
```
Expected: All 3 `test_preview_set_arc_*` tests PASS.

- [ ] **Step 5: Run all new tests together**

```bash
uv run pytest tests/test_resources/test_knowledge.py \
             tests/test_resources/test_snapshot.py \
             tests/test_prompts/test_dj_expert_session.py \
             tests/test_optimization/test_preview.py \
             tests/test_tools/test_candidate_pool.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Run full type check and architecture check**

```bash
uv run mypy app/controllers/tools/sets.py app/controllers/tools/candidate_pool.py
uv run lint-imports
```
Expected: no errors.

- [ ] **Step 7: Run full test suite to verify no regressions**

```bash
uv run pytest -x -q
```
Expected: All tests PASS (existing + new).

- [ ] **Step 8: Commit**

```bash
git add app/controllers/tools/sets.py \
        tests/test_tools/test_candidate_pool.py
git commit -m "feat: add preview_set_arc non-destructive arc evaluation tool"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `knowledge://vocabulary` with all 15 subgenres | Task 1 |
| `knowledge://subgenre-culture` with artists, set_position, flows_from/into | Task 1 |
| `knowledge://set-dynamics` with 5 sections | Task 1 |
| `knowledge://dancefloor-psychology` with crowd states | Task 1 |
| `library://snapshot` aggregating status + mood distribution + playlists | Task 2 |
| `dj_expert_session(goal?)` prompt reading 8 resources + behavioral instructions | Task 3 |
| `get_candidate_pool` with all 7 params, read-only, no DB writes | Task 5 |
| Pure `preview_arc` logic in `app/optimization/` | Task 4 |
| `preview_set_arc` tool wrapping pure logic | Task 6 |
| Existing tools untouched | All tasks — only `sets.py` modified (additive) |
| No schema changes | Confirmed — no migration needed |

**Placeholder scan:** All code blocks are complete. No TBD or TODO markers in implementation steps.

**Type consistency:**
- `PreviewResult` dataclass defined in Task 4, imported in Task 6 ✓
- `FeatureRepository` imported from `app.db.repositories.feature` in both tools ✓
- `get_feature_repo` from `app.controllers.dependencies` ✓
- `TEMPLATES` already imported in `sets.py` — used in `preview_set_arc` ✓
- `map_domain_errors` decorator already imported in `sets.py` ✓
- `ANNOTATIONS_READ_ONLY`, `ICON_SETS`, `TOOL_META`, `ToolCategory` already in `sets.py` ✓
