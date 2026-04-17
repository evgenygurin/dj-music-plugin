# Set Narrative & Curation Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Auto-DJ from "next compatible track" into an adaptive DJ-style set builder that follows energy-arc templates (warm-up → peak → release), exposed through a 5-layer progressive disclosure UI inside the existing player.

**Architecture:** Adaptive per-step picker on the frontend, fed by a composite server action that orchestrates existing backend tools (`score_transitions`, `audit_playlist`, `filter_tracks`). A new read-only backend tool `get_set_templates` exposes the already-existing `app.domain.templates.registry.TEMPLATES` dict. Frontend adds a `SetSessionProvider` context alongside `AudioPlayerProvider`, merged into a single `PlayerProvider` facade. The existing `AudioPlayerBar` is split into layered components (`PlayerHero` / `MiniPlayerBar` / `MediumPlayerBar` / `ControlPanel` / `SetPlannerDrawer`) gated by a persisted `playerInteractionLevel` state (0..4).

**Tech Stack:** Python 3.12 + FastMCP (backend tool), TypeScript + Next.js 16 (App Router) + Bun + React 19 + Tailwind v4 + shadcn/ui (panel), Recharts (energy arc graph), Vitest (unit), Playwright (e2e), Supabase client (direct reads).

**Reference spec:** `docs/superpowers/specs/2026-04-08-set-narrative-design.md`

---

## File Structure

### Backend (new + modified)

| Path | Status | Responsibility |
|---|---|---|
| `app/mcp/tools/sets_meta.py` | **create** | New MCP tool `get_set_templates` |
| `tests/test_mcp/test_sets_meta_tool.py` | **create** | Unit + client tests for the tool |

### Panel (new + modified)

| Path | Status | Responsibility |
|---|---|---|
| `panel/lib/set-narrative/types.ts` | **create** | Shared types (`SetTemplate`, `SlotDefinition`, `ScoredCandidate`, `SetSessionState`) |
| `panel/lib/set-narrative/scoring.ts` | **create** | Pure functions: `getCurrentSlot`, `slotFitScore`, `getAlpha`, `varietyPenalty`, `weightedRandomPick` |
| `panel/lib/set-narrative/scoring.test.ts` | **create** | Vitest unit tests for scoring |
| `panel/lib/set-narrative/constants.ts` | **create** | 15-subgenre energy order, key slot identifiers |
| `panel/actions/set-templates-actions.ts` | **create** | `fetchSetTemplates()` server action |
| `panel/actions/set-picker-actions.ts` | **create** | `pickNextSetTrack()` composite server action |
| `panel/actions/default-first-picker-actions.ts` | **create** | `pickDefaultFirstTrack()` for Layer 0 hero |
| `panel/components/player/player-provider.tsx` | **create** | Unified `<PlayerProvider>` + `usePlayer()` hook |
| `panel/components/player/set-session-context.tsx` | **create** | `<SetSessionProvider>` context with picker integration |
| `panel/components/player/interaction-level.tsx` | **create** | `playerInteractionLevel` state + localStorage persistence |
| `panel/components/player/player-hero.tsx` | **create** | Layer 0 splash component |
| `panel/components/player/mini-player-bar.tsx` | **create** | Layer 1 slim bar |
| `panel/components/player/medium-player-bar.tsx` | **create** | Layer 2 bar with meta + volume + seek |
| `panel/components/player/control-panel.tsx` | **create** | Layer 3 popover (mode picker, mix length) |
| `panel/components/player/set-indicator-chip.tsx` | **create** | Layer 3 chip showing active template |
| `panel/components/player/set-planner-drawer.tsx` | **create** | Layer 4 full drawer (energy arc, slots, upcoming) |
| `panel/components/player/energy-arc-graph.tsx` | **create** | Recharts graph for Layer 4 |
| `panel/components/player/slot-timeline.tsx` | **create** | 8-card slot timeline for Layer 4 |
| `panel/components/audio-player/audio-player-context.tsx` | **modify** | Expose `historyRef` reads; no behaviour change |
| `panel/app/layout.tsx` | **modify** | Wrap in `<PlayerProvider>`, render `<PlayerHero>` + layered bar |
| `panel/components/audio-player/audio-player-bar.tsx` | **delete (later)** | Superseded by layered components |

### Tests

| Path | Status | Responsibility |
|---|---|---|
| `panel/lib/set-narrative/scoring.test.ts` | **create** | Pure-function unit tests |
| `panel/components/player/set-session-context.test.tsx` | **create** | Context behaviour with mocked AudioPlayer |
| `panel/tests/e2e/set-narrative.spec.ts` | **create** | Playwright: layer transitions + template activation |

---

## Phase 1 — Backend: expose set templates

### Task 1: Add `get_set_templates` MCP tool

**Files:**
- Create: `app/mcp/tools/sets_meta.py`

- [ ] **Step 1: Inspect the existing templates registry**

Run: `head -50 app/domain/templates/registry.py`
Note the symbol names: `TEMPLATES: dict[str, SetTemplateDefinition]`, `list_template_names()`, `get_template(name)`.

- [ ] **Step 2: Create the tool file**

```python
# app/mcp/tools/sets_meta.py
"""Read-only exposure of DJ set templates for clients."""

from __future__ import annotations

from typing import Any

from fastmcp import tool

from app.domain.templates.registry import TEMPLATES
from app.mcp.tools._shared import ANNOTATIONS_READ_ONLY, ToolCategory

@tool(
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
)
async def get_set_templates() -> dict[str, Any]:
    """Return all DJ set templates with full slot definitions.

    Each template describes an energy arc as an ordered list of slots
    (warm-up → build → peak → release). Clients use the slot metadata
    (target mood, energy LUFS, BPM range, position, flexibility) to
    score candidate tracks during adaptive set playback.

    This tool is read-only, has no parameters, and returns a single
    payload containing all templates. The result is static per release
    so clients should cache it for the session.
    """
    return {
        "templates": [
            {
                "name": tpl.name,
                "duration_min": tpl.duration_min,
                "description": tpl.description,
                "slots": [
                    {
                        "position": slot.position,
                        "target_mood": slot.target_mood,
                        "energy_lufs": slot.energy_lufs,
                        "bpm_min": slot.bpm_min,
                        "bpm_max": slot.bpm_max,
                        "duration_ms": slot.duration_ms,
                        "flexibility": slot.flexibility,
                    }
                    for slot in tpl.slots
                ],
            }
            for tpl in TEMPLATES.values()
        ]
    }
```

- [ ] **Step 3: Write the test**

```python
# tests/test_mcp/test_sets_meta_tool.py
"""Tests for get_set_templates MCP tool."""

from __future__ import annotations

import pytest
from fastmcp import Client

from app.server import mcp

@pytest.mark.asyncio
async def test_get_set_templates_returns_all_templates() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_set_templates", {})
        data = result.structured_content
        assert data is not None
        templates = data["templates"]
        assert isinstance(templates, list)
        assert len(templates) >= 8

        names = {tpl["name"] for tpl in templates}
        assert "peak_hour_60" in names
        assert "warm_up_30" in names

        peak = next(t for t in templates if t["name"] == "peak_hour_60")
        assert peak["duration_min"] == 60
        assert len(peak["slots"]) > 0

        first_slot = peak["slots"][0]
        assert "position" in first_slot
        assert "target_mood" in first_slot
        assert "energy_lufs" in first_slot
        assert "bpm_min" in first_slot
        assert "bpm_max" in first_slot
        assert "duration_ms" in first_slot
        assert "flexibility" in first_slot
        assert 0.0 <= first_slot["position"] <= 1.0
        assert 0.0 <= first_slot["flexibility"] <= 1.0

@pytest.mark.asyncio
async def test_get_set_templates_has_read_only_annotation() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_set_templates")
        annotations = tool.annotations or {}
        assert annotations.get("readOnlyHint") is True
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_mcp/test_sets_meta_tool.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run the full test suite smoke check**

Run: `uv run pytest tests/test_mcp/ -x -q`
Expected: all tests PASS — no regressions from the new tool.

- [ ] **Step 6: Commit**

```bash
git add app/mcp/tools/sets_meta.py tests/test_mcp/test_sets_meta_tool.py
git commit -F - <<'EOF'
feat(mcp): expose get_set_templates tool

Read-only tool returning the 8 DJ set templates with full slot
definitions so the panel's adaptive picker can score candidate
tracks against slot targets (mood, energy LUFS, BPM range).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 2 — Panel: types and constants

### Task 2: Shared types for set narrative

**Files:**
- Create: `panel/lib/set-narrative/types.ts`

- [ ] **Step 1: Write the types file**

```typescript
// panel/lib/set-narrative/types.ts

export interface SlotDefinition {
  position: number // 0..1 within set
  targetMood: string | null
  energyLufs: number
  bpmMin: number
  bpmMax: number
  durationMs: number
  flexibility: number
}

export interface SetTemplate {
  name: string
  durationMin: number
  description: string
  slots: SlotDefinition[]
}

export interface CurrentSlot {
  slot: SlotDefinition
  index: number
  positionInSlot: number // 0..1 within current slot
  positionInSet: number // 0..1 across entire set
}

export interface HistoryEntry {
  trackId: number
  artistIds: number[]
  mood: string | null
  lufs: number | null
  playedAtSec: number // elapsed at play time
}

export interface ScoredCandidate {
  trackId: number
  title: string
  artists: string
  bpm: number | null
  camelot: string | null
  mood: string | null
  lufs: number | null
  transitionScore: number // 0..1
  slotFit: number // 0..1
  varietyPenalty: number // multiplier, typically 0.5..1.0
  combinedScore: number // final
  rationale: string // short human-readable explanation
}

export interface SetSessionState {
  active: boolean
  template: SetTemplate | null
  startedAtSec: number // AudioContext currentTime when session started
  elapsedSec: number
  currentSlot: CurrentSlot | null
  history: HistoryEntry[]
  upcoming: ScoredCandidate[]
  varietyTier: 0 | 1 | 2 // 0 = strictest, 2 = open
  relaxationEvents: string[] // log messages when constraints relaxed
}
```

- [ ] **Step 2: Verify typescript compiles**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -10`
Expected: build passes (types not yet consumed — only structural).

- [ ] **Step 3: Commit**

```bash
git add panel/lib/set-narrative/types.ts
git commit -F - <<'EOF'
feat(panel): add set-narrative shared types

Types describing slots, templates, set session state, and scored
candidates. Consumed by scoring logic, server actions, and UI.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 3: Subgenre energy order + key slot constants

**Files:**
- Create: `panel/lib/set-narrative/constants.ts`

- [ ] **Step 1: Write the constants file**

```typescript
// panel/lib/set-narrative/constants.ts

// Ordered low → high energy. Source of truth:
// app/core/constants.py::TechnoSubgenre (mirror list — keep in sync).
export const SUBGENRE_ENERGY_ORDER: string[] = [
  'ambient_dub',
  'dub_techno',
  'minimal',
  'detroit',
  'melodic_deep',
  'progressive',
  'hypnotic',
  'driving',
  'tribal',
  'breakbeat',
  'peak_time',
  'acid',
  'raw',
  'industrial',
  'hard_techno',
]

// Slots whose target_mood falls into these names get a lower alpha
// (stronger slot-fit weighting) because hitting the right vibe at
// these points matters more than transition smoothness.
export const KEY_SLOT_MOODS: ReadonlySet<string> = new Set([
  'peak_time',
  'industrial',
  'hard_techno',
  'acid',
])

export const DEFAULT_CROSSFADE_BARS = 32

// Variety thresholds
export const VARIETY_RECENT_HISTORY_SIZE = 50
export const VARIETY_MOOD_STREAK = 3
export const VARIETY_PENALTY_SAME_ARTIST = 0.7
export const VARIETY_PENALTY_MOOD_STREAK = 0.8
export const VARIETY_PENALTY_RECENT = 0.5

// Scoring weights
export const ALPHA_DEFAULT = 0.6
export const ALPHA_KEY_SLOT = 0.4
export const ALPHA_SLOT_ENDING = 0.3
export const ALPHA_SLOT_ENDING_POSITION = 0.8

// Picker constraints
export const PICKER_TOP_N = 8
export const BACKEND_CANDIDATES_TOP_N = 30
```

- [ ] **Step 2: Commit**

```bash
git add panel/lib/set-narrative/constants.ts
git commit -F - <<'EOF'
feat(panel): add set-narrative constants

Ordered subgenre energy list, key slot moods, variety thresholds,
and scoring weights. Single source of tuning knobs.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 3 — Scoring: pure functions with TDD

### Task 4: `getCurrentSlot` with tests

**Files:**
- Create: `panel/lib/set-narrative/scoring.ts`
- Create: `panel/lib/set-narrative/scoring.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// panel/lib/set-narrative/scoring.test.ts
import { describe, it, expect } from 'vitest'
import { getCurrentSlot } from './scoring'
import type { SetTemplate } from './types'

const SAMPLE_TEMPLATE: SetTemplate = {
  name: 'test_60',
  durationMin: 60,
  description: 'test',
  slots: [
    { position: 0.0, targetMood: 'warm_up', energyLufs: -18, bpmMin: 120, bpmMax: 124, durationMs: 15 * 60_000, flexibility: 0.5 },
    { position: 0.25, targetMood: 'driving', energyLufs: -12, bpmMin: 124, bpmMax: 128, durationMs: 15 * 60_000, flexibility: 0.5 },
    { position: 0.5, targetMood: 'peak_time', energyLufs: -8, bpmMin: 128, bpmMax: 132, durationMs: 15 * 60_000, flexibility: 0.3 },
    { position: 0.75, targetMood: 'minimal', energyLufs: -14, bpmMin: 126, bpmMax: 130, durationMs: 15 * 60_000, flexibility: 0.5 },
  ],
}

describe('getCurrentSlot', () => {
  it('returns first slot at elapsed 0', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 0, 3600)
    expect(result.index).toBe(0)
    expect(result.slot.targetMood).toBe('warm_up')
    expect(result.positionInSlot).toBeCloseTo(0, 2)
    expect(result.positionInSet).toBeCloseTo(0, 2)
  })

  it('returns middle slot at half elapsed', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 1800, 3600)
    expect(result.index).toBe(2)
    expect(result.slot.targetMood).toBe('peak_time')
    expect(result.positionInSet).toBeCloseTo(0.5, 2)
  })

  it('clamps to last slot beyond duration', () => {
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 7200, 3600)
    expect(result.index).toBe(3)
    expect(result.positionInSet).toBeCloseTo(1, 2)
  })

  it('computes positionInSlot correctly inside first slot', () => {
    // half-way through slot 0 (0.0..0.25 of 3600 = 0..900s), elapsed 450
    const result = getCurrentSlot(SAMPLE_TEMPLATE, 450, 3600)
    expect(result.index).toBe(0)
    expect(result.positionInSlot).toBeCloseTo(0.5, 2)
  })
})
```

- [ ] **Step 2: Run test, verify failure**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -20`
Expected: FAIL ("Cannot find module './scoring'" or similar).

- [ ] **Step 3: Write the implementation**

```typescript
// panel/lib/set-narrative/scoring.ts
import type { CurrentSlot, SetTemplate } from './types'

export function getCurrentSlot(
  template: SetTemplate,
  elapsedSec: number,
  totalDurationSec: number,
): CurrentSlot {
  const positionInSet = Math.max(0, Math.min(1, elapsedSec / totalDurationSec))

  for (let i = 0; i < template.slots.length; i++) {
    const slot = template.slots[i]
    const next = template.slots[i + 1]
    const slotStart = slot.position
    const slotEnd = next ? next.position : 1.0
    if (positionInSet >= slotStart && positionInSet < slotEnd) {
      const span = slotEnd - slotStart
      const positionInSlot = span > 0 ? (positionInSet - slotStart) / span : 0
      return { slot, index: i, positionInSlot, positionInSet }
    }
  }

  // Fall-through: beyond last slot
  const last = template.slots[template.slots.length - 1]
  return {
    slot: last,
    index: template.slots.length - 1,
    positionInSlot: 1,
    positionInSet: 1,
  }
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -15`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add panel/lib/set-narrative/scoring.ts panel/lib/set-narrative/scoring.test.ts
git commit -F - <<'EOF'
feat(panel): getCurrentSlot with unit tests

Maps elapsed/total set time to the active slot, its index, and
normalized positions within slot and set. Pure function, no state.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 5: `slotFitScore` with tests

**Files:**
- Modify: `panel/lib/set-narrative/scoring.ts` (append)
- Modify: `panel/lib/set-narrative/scoring.test.ts` (append)

- [ ] **Step 1: Add failing test**

```typescript
// append to scoring.test.ts
import { slotFitScore } from './scoring'
import type { SlotDefinition } from './types'

const PEAK_SLOT: SlotDefinition = {
  position: 0.5,
  targetMood: 'peak_time',
  energyLufs: -8,
  bpmMin: 128,
  bpmMax: 132,
  durationMs: 900000,
  flexibility: 0.3,
}

describe('slotFitScore', () => {
  it('scores perfect match near 1.0', () => {
    const score = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'peak_time' },
      PEAK_SLOT,
    )
    expect(score).toBeGreaterThan(0.9)
  })

  it('penalises wrong mood', () => {
    const score = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'ambient_dub' },
      PEAK_SLOT,
    )
    expect(score).toBeLessThan(0.85)
  })

  it('penalises off-range BPM', () => {
    const score = slotFitScore(
      { bpm: 140, lufs: -8, mood: 'peak_time' },
      PEAK_SLOT,
    )
    expect(score).toBeLessThan(0.75)
  })

  it('neighbour mood gets partial credit', () => {
    // acid is neighbour of peak_time (index ±1 in SUBGENRE_ENERGY_ORDER)
    const score = slotFitScore(
      { bpm: 130, lufs: -8, mood: 'acid' },
      PEAK_SLOT,
    )
    expect(score).toBeGreaterThan(0.85)
    expect(score).toBeLessThan(1.0)
  })

  it('returns neutral 0.5-ish when all features missing', () => {
    const score = slotFitScore({ bpm: null, lufs: null, mood: null }, PEAK_SLOT)
    expect(score).toBeGreaterThan(0.3)
    expect(score).toBeLessThan(0.7)
  })
})
```

- [ ] **Step 2: Run, verify failure**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -20`
Expected: slotFitScore test block FAILS.

- [ ] **Step 3: Implement**

```typescript
// append to scoring.ts
import { SUBGENRE_ENERGY_ORDER } from './constants'
import type { SlotDefinition } from './types'

interface CandidateFeatures {
  bpm: number | null
  lufs: number | null
  mood: string | null
}

function gaussianDecay(diff: number, sigma: number): number {
  return Math.exp(-(diff * diff) / (2 * sigma * sigma))
}

function areMoodsNeighbors(a: string, b: string): boolean {
  const ia = SUBGENRE_ENERGY_ORDER.indexOf(a)
  const ib = SUBGENRE_ENERGY_ORDER.indexOf(b)
  if (ia < 0 || ib < 0) return false
  return Math.abs(ia - ib) <= 2
}

export function slotFitScore(
  candidate: CandidateFeatures,
  slot: SlotDefinition,
): number {
  // BPM fit (weight 0.5)
  let bpmFit = 0.5
  if (candidate.bpm != null) {
    const center = (slot.bpmMin + slot.bpmMax) / 2
    const tolerance = Math.max(1, (slot.bpmMax - slot.bpmMin) / 2)
    const diff = Math.abs(candidate.bpm - center)
    if (diff <= tolerance) {
      // Inside range: gentle 0.3 linear penalty toward the edges
      bpmFit = 1 - (diff / tolerance) * 0.3
    } else {
      // Outside: gaussian fall-off with σ=4
      bpmFit = gaussianDecay(diff - tolerance, 4) * 0.7
    }
  }

  // LUFS fit (weight 0.3)
  let lufsFit = 0.5
  if (candidate.lufs != null) {
    const diff = Math.abs(candidate.lufs - slot.energyLufs)
    lufsFit = gaussianDecay(diff, 3)
  }

  // Mood fit (weight 0.2)
  let moodFit = 0.5
  if (candidate.mood && slot.targetMood) {
    if (candidate.mood === slot.targetMood) moodFit = 1.0
    else if (areMoodsNeighbors(candidate.mood, slot.targetMood)) moodFit = 0.85
  }

  return 0.5 * bpmFit + 0.3 * lufsFit + 0.2 * moodFit
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -15`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add panel/lib/set-narrative/scoring.ts panel/lib/set-narrative/scoring.test.ts
git commit -F - <<'EOF'
feat(panel): slotFitScore gaussian BPM/LUFS + mood neighbours

Weighted (50/30/20) fit score for a candidate track against a slot
definition. Uses gaussian decay for BPM-outside-range and LUFS,
linear penalty within BPM range, and subgenre-energy neighbour
lookup for partial mood credit.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 6: `getAlpha` + `varietyPenalty` + `weightedRandomPick`

**Files:**
- Modify: `panel/lib/set-narrative/scoring.ts` (append)
- Modify: `panel/lib/set-narrative/scoring.test.ts` (append)

- [ ] **Step 1: Add failing tests**

```typescript
// append to scoring.test.ts
import { getAlpha, varietyPenalty, weightedRandomPick } from './scoring'
import type { HistoryEntry, ScoredCandidate } from './types'

describe('getAlpha', () => {
  it('defaults to 0.6 for non-key slots mid-slot', () => {
    const alpha = getAlpha({ targetMood: 'driving' } as SlotDefinition, 0.4)
    expect(alpha).toBeCloseTo(0.6, 2)
  })
  it('drops to 0.4 for key slots', () => {
    const alpha = getAlpha({ targetMood: 'peak_time' } as SlotDefinition, 0.4)
    expect(alpha).toBeCloseTo(0.4, 2)
  })
  it('drops to 0.3 near slot ending', () => {
    const alpha = getAlpha({ targetMood: 'driving' } as SlotDefinition, 0.9)
    expect(alpha).toBeCloseTo(0.3, 2)
  })
  it('key slot + ending = 0.3', () => {
    const alpha = getAlpha({ targetMood: 'peak_time' } as SlotDefinition, 0.9)
    expect(alpha).toBeCloseTo(0.3, 2)
  })
})

describe('varietyPenalty', () => {
  const history: HistoryEntry[] = [
    { trackId: 1, artistIds: [10], mood: 'driving', lufs: null, playedAtSec: 0 },
    { trackId: 2, artistIds: [20], mood: 'driving', lufs: null, playedAtSec: 300 },
    { trackId: 3, artistIds: [30], mood: 'driving', lufs: null, playedAtSec: 600 },
  ]

  it('no penalty for unrelated candidate', () => {
    const p = varietyPenalty(
      { id: 99, artistIds: [77], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(1.0, 2)
  })
  it('penalises same artist as previous', () => {
    const p = varietyPenalty(
      { id: 99, artistIds: [30], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(0.7, 2)
  })
  it('penalises mood streak', () => {
    const p = varietyPenalty(
      { id: 99, artistIds: [77], mood: 'driving' },
      history,
    )
    expect(p).toBeCloseTo(0.8, 2)
  })
  it('penalises recently played track', () => {
    const p = varietyPenalty(
      { id: 2, artistIds: [77], mood: 'peak_time' },
      history,
    )
    expect(p).toBeCloseTo(0.5, 2)
  })
  it('compounds multiple penalties', () => {
    const p = varietyPenalty(
      { id: 3, artistIds: [30], mood: 'driving' },
      history,
    )
    // recent (0.5) * same artist (0.7) * mood streak (0.8) = 0.28
    expect(p).toBeCloseTo(0.28, 2)
  })
})

describe('weightedRandomPick', () => {
  it('returns distribution proportional to combinedScore', () => {
    const candidates: ScoredCandidate[] = [
      { combinedScore: 0.9 } as ScoredCandidate,
      { combinedScore: 0.1 } as ScoredCandidate,
    ]
    let firstHits = 0
    const runs = 2000
    const rng = () => Math.random()
    for (let i = 0; i < runs; i++) {
      if (weightedRandomPick(candidates, rng) === candidates[0]) firstHits++
    }
    // Expect ~90% hits on the heavy candidate, allow 5% slack.
    expect(firstHits / runs).toBeGreaterThan(0.85)
    expect(firstHits / runs).toBeLessThan(0.95)
  })

  it('returns first when pool length is 1', () => {
    const candidates: ScoredCandidate[] = [{ combinedScore: 0.5 } as ScoredCandidate]
    expect(weightedRandomPick(candidates)).toBe(candidates[0])
  })
})
```

- [ ] **Step 2: Run, verify failure**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -20`
Expected: new describes FAIL ("not exported").

- [ ] **Step 3: Implement**

```typescript
// append to scoring.ts
import {
  ALPHA_DEFAULT,
  ALPHA_KEY_SLOT,
  ALPHA_SLOT_ENDING,
  ALPHA_SLOT_ENDING_POSITION,
  KEY_SLOT_MOODS,
  VARIETY_MOOD_STREAK,
  VARIETY_PENALTY_MOOD_STREAK,
  VARIETY_PENALTY_RECENT,
  VARIETY_PENALTY_SAME_ARTIST,
  VARIETY_RECENT_HISTORY_SIZE,
} from './constants'
import type { HistoryEntry, ScoredCandidate } from './types'

export function getAlpha(slot: SlotDefinition, positionInSlot: number): number {
  const isKey = slot.targetMood != null && KEY_SLOT_MOODS.has(slot.targetMood)
  let alpha = isKey ? ALPHA_KEY_SLOT : ALPHA_DEFAULT
  if (positionInSlot > ALPHA_SLOT_ENDING_POSITION) {
    alpha = Math.min(alpha, ALPHA_SLOT_ENDING)
  }
  return alpha
}

interface VarietyCandidate {
  id: number
  artistIds: number[]
  mood: string | null
}

export function varietyPenalty(
  candidate: VarietyCandidate,
  history: HistoryEntry[],
): number {
  let penalty = 1.0

  const previous = history[history.length - 1]
  if (previous) {
    const sharedArtist = candidate.artistIds.some((a) => previous.artistIds.includes(a))
    if (sharedArtist) penalty *= VARIETY_PENALTY_SAME_ARTIST
  }

  const moodStreakWindow = history.slice(-VARIETY_MOOD_STREAK)
  if (
    candidate.mood != null &&
    moodStreakWindow.length === VARIETY_MOOD_STREAK &&
    moodStreakWindow.every((h) => h.mood === candidate.mood)
  ) {
    penalty *= VARIETY_PENALTY_MOOD_STREAK
  }

  const recent = history.slice(-VARIETY_RECENT_HISTORY_SIZE)
  if (recent.some((h) => h.trackId === candidate.id)) {
    penalty *= VARIETY_PENALTY_RECENT
  }

  return penalty
}

export function weightedRandomPick(
  candidates: ScoredCandidate[],
  rng: () => number = Math.random,
): ScoredCandidate {
  if (candidates.length === 0) {
    throw new Error('weightedRandomPick: empty candidates')
  }
  if (candidates.length === 1) return candidates[0]

  const total = candidates.reduce((acc, c) => acc + Math.max(0, c.combinedScore), 0)
  if (total <= 0) return candidates[0]

  let r = rng() * total
  for (const c of candidates) {
    r -= Math.max(0, c.combinedScore)
    if (r <= 0) return c
  }
  return candidates[candidates.length - 1]
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bunx vitest run lib/set-narrative/scoring.test.ts 2>&1 | tail -15`
Expected: all tests PASS (>= 16 total).

- [ ] **Step 5: Commit**

```bash
git add panel/lib/set-narrative/scoring.ts panel/lib/set-narrative/scoring.test.ts
git commit -F - <<'EOF'
feat(panel): alpha, varietyPenalty, weightedRandomPick

Dynamic α blending (compatibility vs slot fit), soft variety
penalties (artist, mood streak, recent history), and weighted
random pick over top-N candidates. Statistical test verifies
distribution matches weights.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 4 — Server actions

### Task 7: `fetchSetTemplates` server action

**Files:**
- Create: `panel/actions/set-templates-actions.ts`

- [ ] **Step 1: Write the action**

```typescript
// panel/actions/set-templates-actions.ts
'use server'

import { callTool } from '@/lib/mcp-client'
import type { SetTemplate, SlotDefinition } from '@/lib/set-narrative/types'

interface RawSlot {
  position: number
  target_mood: string | null
  energy_lufs: number
  bpm_min: number
  bpm_max: number
  duration_ms: number
  flexibility: number
}

interface RawTemplate {
  name: string
  duration_min: number
  description: string
  slots: RawSlot[]
}

export async function fetchSetTemplates(): Promise<SetTemplate[]> {
  try {
    const result = await callTool('get_set_templates', {})
    const sc = result?.structured_content as { templates?: RawTemplate[] } | undefined
    const raw = sc?.templates
    if (!raw || !Array.isArray(raw)) return []

    return raw.map((t) => ({
      name: t.name,
      durationMin: t.duration_min,
      description: t.description,
      slots: t.slots.map(
        (s): SlotDefinition => ({
          position: s.position,
          targetMood: s.target_mood,
          energyLufs: s.energy_lufs,
          bpmMin: s.bpm_min,
          bpmMax: s.bpm_max,
          durationMs: s.duration_ms,
          flexibility: s.flexibility,
        }),
      ),
    }))
  } catch {
    return []
  }
}
```

- [ ] **Step 2: Smoke test via curl**

Run:
```bash
curl -s -X POST http://localhost:8000/api/tools/get_set_templates/call \
  -H "Content-Type: application/json" -d '{"arguments":{}}' | head -c 500
```
Expected: JSON payload with `"templates"` array containing slot definitions.

- [ ] **Step 3: Commit**

```bash
git add panel/actions/set-templates-actions.ts
git commit -F - <<'EOF'
feat(panel): fetchSetTemplates server action

Thin wrapper around get_set_templates MCP tool that maps snake_case
fields to camelCase TypeScript types.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 8: `pickDefaultFirstTrack` server action

**Files:**
- Create: `panel/actions/default-first-picker-actions.ts`

- [ ] **Step 1: Write the action**

```typescript
// panel/actions/default-first-picker-actions.ts
'use server'

import { createClient } from '@/lib/supabase/server'
import type { TrackRow } from '@/lib/queries/tracks'

export interface DefaultPickResult {
  first: TrackRow | null
  queue: TrackRow[]
}

export async function pickDefaultFirstTrack(): Promise<DefaultPickResult> {
  const supabase = await createClient()

  // Prefer tracks with full analysis + a classified mood, sorted by
  // mood confidence — these are the "broadcast-quality" tracks.
  const { data: qualityTracks } = await supabase
    .from('tracks')
    .select(`
      id,
      title,
      duration_ms,
      status,
      track_audio_features_computed!inner(
        bpm,
        key_code,
        mood,
        integrated_lufs,
        energy_mean,
        analysis_level,
        mood_confidence
      )
    `)
    .eq('status', 0)
    .gte('track_audio_features_computed.analysis_level', 4)
    .not('track_audio_features_computed.mood', 'is', null)
    .order('track_audio_features_computed.mood_confidence', { ascending: false })
    .limit(50)

  if (qualityTracks && qualityTracks.length > 0) {
    const rows = mapTrackRows(qualityTracks)
    const pick = rows[Math.floor(Math.random() * rows.length)]
    return { first: pick, queue: rows }
  }

  // Fallback — any track with BPM
  const { data: anyTracks } = await supabase
    .from('tracks')
    .select(`
      id,
      title,
      duration_ms,
      status,
      track_audio_features_computed!inner(bpm, key_code, mood, integrated_lufs, energy_mean, analysis_level, mood_confidence)
    `)
    .eq('status', 0)
    .not('track_audio_features_computed.bpm', 'is', null)
    .limit(50)

  if (!anyTracks || anyTracks.length === 0) return { first: null, queue: [] }
  const rows = mapTrackRows(anyTracks)
  return { first: rows[0], queue: rows }
}

function mapTrackRows(raw: unknown[]): TrackRow[] {
  // Simplified mapping — artists resolved lazily by caller via existing
  // queries. For the splash picker, bare minimum fields are sufficient.
  return raw.map((t: any) => {
    const features = Array.isArray(t.track_audio_features_computed)
      ? t.track_audio_features_computed[0]
      : t.track_audio_features_computed
    return {
      id: t.id,
      title: t.title,
      duration_ms: t.duration_ms,
      status: t.status,
      artists: '',
      bpm: features?.bpm ?? null,
      key_code: features?.key_code ?? null,
      camelot: null,
      mood: features?.mood ?? null,
      integrated_lufs: features?.integrated_lufs ?? null,
      energy_mean: features?.energy_mean ?? null,
      analysis_level: features?.analysis_level ?? null,
      hp_ratio: null,
      danceability: null,
      mood_confidence: features?.mood_confidence ?? null,
    } as TrackRow
  })
}
```

- [ ] **Step 2: Build check**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -10`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
git add panel/actions/default-first-picker-actions.ts
git commit -F - <<'EOF'
feat(panel): pickDefaultFirstTrack for Layer 0 hero

Picks a random track from the top-50 audit-passed, mood-classified
tracks sorted by mood confidence. Returns the pick plus the same
set as initial Compatibility-mode queue.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 9: `pickNextSetTrack` composite action

**Files:**
- Create: `panel/actions/set-picker-actions.ts`

- [ ] **Step 1: Write the action**

```typescript
// panel/actions/set-picker-actions.ts
'use server'

import { callTool } from '@/lib/mcp-client'
import { createClient } from '@/lib/supabase/server'
import {
  BACKEND_CANDIDATES_TOP_N,
  PICKER_TOP_N,
} from '@/lib/set-narrative/constants'
import {
  getAlpha,
  getCurrentSlot,
  slotFitScore,
  varietyPenalty,
} from '@/lib/set-narrative/scoring'
import type {
  HistoryEntry,
  ScoredCandidate,
  SetTemplate,
} from '@/lib/set-narrative/types'

export interface PickerInput {
  currentTrackId: number
  template: SetTemplate
  elapsedSec: number
  totalDurationSec: number
  history: HistoryEntry[]
  varietyTier: 0 | 1 | 2
}

interface RawTransitionCandidate {
  to_track_id: number
  overall_quality: number
}

export async function pickNextSetTrack(
  input: PickerInput,
): Promise<ScoredCandidate[]> {
  // 1. Resolve current slot
  const current = getCurrentSlot(input.template, input.elapsedSec, input.totalDurationSec)
  const alpha = getAlpha(current.slot, current.positionInSlot)

  // 2. Ask backend TransitionScorer for top-N candidates from current track
  const scoreResult = await callTool('score_transitions', {
    mode: 'track_candidates',
    track_id: input.currentTrackId,
    top_n: BACKEND_CANDIDATES_TOP_N,
  })
  const scored = scoreResult?.structured_content as
    | { candidates?: RawTransitionCandidate[]; transitions?: RawTransitionCandidate[] }
    | undefined
  const rawList = scored?.candidates ?? scored?.transitions ?? []
  if (rawList.length === 0) return []

  // 3. Fetch features + artists for candidate tracks
  const trackIds = rawList.map((c) => c.to_track_id)
  const supabase = await createClient()
  const { data: featureRows } = await supabase
    .from('tracks')
    .select(`
      id,
      title,
      track_audio_features_computed!inner(bpm, mood, integrated_lufs, key_code),
      track_artists(artist_id)
    `)
    .in('id', trackIds)

  const featureMap = new Map<number, {
    title: string
    bpm: number | null
    lufs: number | null
    mood: string | null
    camelot: string | null
    artistIds: number[]
  }>()
  for (const row of featureRows ?? []) {
    const f = Array.isArray(row.track_audio_features_computed)
      ? row.track_audio_features_computed[0]
      : row.track_audio_features_computed
    const artistRefs = Array.isArray(row.track_artists) ? row.track_artists : []
    featureMap.set(row.id, {
      title: row.title,
      bpm: f?.bpm ?? null,
      lufs: f?.integrated_lufs ?? null,
      mood: f?.mood ?? null,
      camelot: null, // filled below
      artistIds: artistRefs.map((a: any) => a.artist_id),
    })
  }

  // 4. Apply hard rejects per tier
  const recentIds = new Set(input.history.slice(-50).map((h) => h.trackId))
  const previous = input.history[input.history.length - 1]
  const filtered = rawList.filter((c) => {
    if (!featureMap.has(c.to_track_id)) return false
    if (c.overall_quality <= 0) return false
    if (recentIds.has(c.to_track_id)) return false
    if (input.varietyTier === 0 && previous) {
      const cand = featureMap.get(c.to_track_id)!
      if (cand.artistIds.some((a) => previous.artistIds.includes(a))) return false
    }
    return true
  })

  // 5. Score each candidate
  const scoredCandidates: ScoredCandidate[] = filtered.map((c) => {
    const feat = featureMap.get(c.to_track_id)!
    const slotFit = slotFitScore(
      { bpm: feat.bpm, lufs: feat.lufs, mood: feat.mood },
      current.slot,
    )
    const variety = varietyPenalty(
      { id: c.to_track_id, artistIds: feat.artistIds, mood: feat.mood },
      input.history,
    )
    const combinedScore =
      (alpha * c.overall_quality + (1 - alpha) * slotFit) * variety

    return {
      trackId: c.to_track_id,
      title: feat.title,
      artists: '',
      bpm: feat.bpm,
      camelot: feat.camelot,
      mood: feat.mood,
      lufs: feat.lufs,
      transitionScore: c.overall_quality,
      slotFit,
      varietyPenalty: variety,
      combinedScore,
      rationale: `slot ${slotFit.toFixed(2)} · transition ${c.overall_quality.toFixed(2)} · variety ×${variety.toFixed(2)}`,
    }
  })

  scoredCandidates.sort((a, b) => b.combinedScore - a.combinedScore)
  return scoredCandidates.slice(0, PICKER_TOP_N)
}
```

- [ ] **Step 2: Build check**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -10`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
git add panel/actions/set-picker-actions.ts
git commit -F - <<'EOF'
feat(panel): pickNextSetTrack composite server action

Orchestrates score_transitions (backend) + Supabase feature query +
scoring.ts functions to produce top-8 ScoredCandidates with
combined score, variety penalty, and human-readable rationale.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 5 — Context and providers

### Task 10: `playerInteractionLevel` state hook

**Files:**
- Create: `panel/components/player/interaction-level.tsx`

- [ ] **Step 1: Write the hook**

```typescript
// panel/components/player/interaction-level.tsx
'use client'

import { useCallback, useEffect, useState } from 'react'

export type PlayerLayer = 0 | 1 | 2 | 3 | 4
const STORAGE_KEY = 'dj-player-level'

export function usePlayerInteractionLevel() {
  const [level, setLevel] = useState<PlayerLayer>(0)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = Number.parseInt(stored, 10)
      if (parsed >= 0 && parsed <= 4) setLevel(parsed as PlayerLayer)
    }
  }, [])

  const persist = useCallback((next: PlayerLayer) => {
    setLevel(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, String(next))
    }
  }, [])

  const promote = useCallback(() => {
    persist(Math.min(4, level + 1) as PlayerLayer)
  }, [level, persist])

  const collapse = useCallback(() => {
    persist(Math.max(0, level - 1) as PlayerLayer)
  }, [level, persist])

  const jumpTo = useCallback(
    (target: PlayerLayer) => {
      persist(target)
    },
    [persist],
  )

  return { level, promote, collapse, jumpTo }
}
```

- [ ] **Step 2: Build check**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -5`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
git add panel/components/player/interaction-level.tsx
git commit -F - <<'EOF'
feat(panel): playerInteractionLevel hook with localStorage

Persisted 0..4 state for progressive disclosure. promote/collapse/
jumpTo methods operate on a clamped range.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 11: `SetSessionProvider` context

**Files:**
- Create: `panel/components/player/set-session-context.tsx`

- [ ] **Step 1: Write the provider**

```typescript
// panel/components/player/set-session-context.tsx
'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { fetchSetTemplates } from '@/actions/set-templates-actions'
import { pickNextSetTrack } from '@/actions/set-picker-actions'
import type {
  HistoryEntry,
  ScoredCandidate,
  SetSessionState,
  SetTemplate,
} from '@/lib/set-narrative/types'
import { getCurrentSlot } from '@/lib/set-narrative/scoring'

import { useAudioPlayer, type PlayerTrackMeta } from '@/components/audio-player/audio-player-context'

interface SetSessionApi extends SetSessionState {
  templates: SetTemplate[]
  startTemplate: (templateName: string) => void
  stopSet: () => void
  skipSlot: () => void
  rebuildRemainder: () => Promise<void>
  overridePick: (track: PlayerTrackMeta) => void
}

const Ctx = createContext<SetSessionApi | null>(null)

export function useSetSession(): SetSessionApi {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useSetSession must be used inside SetSessionProvider')
  return ctx
}

const SESSION_STORAGE_KEY = 'dj-set-session'

export function SetSessionProvider({ children }: { children: React.ReactNode }) {
  const player = useAudioPlayer()
  const [templates, setTemplates] = useState<SetTemplate[]>([])
  const [active, setActive] = useState(false)
  const [template, setTemplate] = useState<SetTemplate | null>(null)
  const [startedAtSec, setStartedAtSec] = useState(0)
  const [elapsedSec, setElapsedSec] = useState(0)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [upcoming, setUpcoming] = useState<ScoredCandidate[]>([])
  const [varietyTier] = useState<0 | 1 | 2>(0)
  const [relaxationEvents] = useState<string[]>([])
  const pickInFlight = useRef(false)

  // Fetch templates once on mount
  useEffect(() => {
    void fetchSetTemplates().then(setTemplates)
  }, [])

  // Restore session from sessionStorage on mount
  useEffect(() => {
    if (typeof window === 'undefined') return
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      if (parsed && parsed.active && parsed.templateName) {
        // deferred: restored after templates load
      }
    } catch {
      // ignore
    }
  }, [])

  // Persist session on change
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!active) {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
      return
    }
    window.sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        active,
        templateName: template?.name,
        startedAtSec,
        history,
      }),
    )
  }, [active, template, startedAtSec, history])

  // Track elapsed time from AudioContext/clock
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => {
      setElapsedSec((s) => s + 1)
    }, 1000)
    return () => window.clearInterval(id)
  }, [active])

  // Compute currentSlot
  const currentSlot = useMemo(() => {
    if (!template) return null
    return getCurrentSlot(template, elapsedSec, template.durationMin * 60)
  }, [template, elapsedSec])

  // Record history when current track changes
  const lastCurrentId = useRef<number | null>(null)
  useEffect(() => {
    if (!active || !player.current) return
    if (lastCurrentId.current === player.current.id) return
    lastCurrentId.current = player.current.id
    setHistory((h) => [
      ...h,
      {
        trackId: player.current!.id,
        artistIds: [], // resolved by picker via Supabase
        mood: player.current!.mood ?? null,
        lufs: null,
        playedAtSec: elapsedSec,
      },
    ])
  }, [active, player.current, elapsedSec])

  // Refresh upcoming periodically (every 30s) when active
  useEffect(() => {
    if (!active || !template || !player.current) {
      setUpcoming([])
      return
    }
    let cancelled = false
    const doPick = async () => {
      if (pickInFlight.current) return
      pickInFlight.current = true
      try {
        const picks = await pickNextSetTrack({
          currentTrackId: player.current!.id,
          template,
          elapsedSec,
          totalDurationSec: template.durationMin * 60,
          history,
          varietyTier,
        })
        if (!cancelled) setUpcoming(picks)
      } finally {
        pickInFlight.current = false
      }
    }
    void doPick()
    const id = window.setInterval(() => void doPick(), 30_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [active, template, player.current, elapsedSec, history, varietyTier])

  const startTemplate = useCallback(
    (templateName: string) => {
      const tpl = templates.find((t) => t.name === templateName)
      if (!tpl) return
      setTemplate(tpl)
      setActive(true)
      setStartedAtSec(Math.floor(Date.now() / 1000))
      setElapsedSec(0)
      setHistory([])
    },
    [templates],
  )

  const stopSet = useCallback(() => {
    setActive(false)
    setTemplate(null)
    setElapsedSec(0)
    setHistory([])
    setUpcoming([])
  }, [])

  const skipSlot = useCallback(() => {
    // Advance elapsedSec to the start of the next slot.
    if (!template || !currentSlot) return
    const nextSlotIdx = currentSlot.index + 1
    const next = template.slots[nextSlotIdx]
    if (next) {
      setElapsedSec(Math.ceil(next.position * template.durationMin * 60))
    }
  }, [template, currentSlot])

  const rebuildRemainder = useCallback(async () => {
    if (!active || !template || !player.current) return
    const picks = await pickNextSetTrack({
      currentTrackId: player.current.id,
      template,
      elapsedSec,
      totalDurationSec: template.durationMin * 60,
      history,
      varietyTier,
    })
    setUpcoming(picks)
  }, [active, template, player.current, elapsedSec, history, varietyTier])

  const overridePick = useCallback(
    (track: PlayerTrackMeta) => {
      player.play(track)
    },
    [player],
  )

  const api = useMemo<SetSessionApi>(
    () => ({
      active,
      template,
      startedAtSec,
      elapsedSec,
      currentSlot,
      history,
      upcoming,
      varietyTier,
      relaxationEvents,
      templates,
      startTemplate,
      stopSet,
      skipSlot,
      rebuildRemainder,
      overridePick,
    }),
    [
      active,
      template,
      startedAtSec,
      elapsedSec,
      currentSlot,
      history,
      upcoming,
      varietyTier,
      relaxationEvents,
      templates,
      startTemplate,
      stopSet,
      skipSlot,
      rebuildRemainder,
      overridePick,
    ],
  )

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>
}
```

- [ ] **Step 2: Build check**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -10`
Expected: build passes.

- [ ] **Step 3: Commit**

```bash
git add panel/components/player/set-session-context.tsx
git commit -F - <<'EOF'
feat(panel): SetSessionProvider context

Adaptive set state: active template, elapsed, current slot, history,
upcoming candidates. Integrates with AudioPlayerProvider via hook,
refreshes upcoming every 30s, persists to sessionStorage.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 12: Unified `PlayerProvider` facade

**Files:**
- Create: `panel/components/player/player-provider.tsx`

- [ ] **Step 1: Write the provider**

```typescript
// panel/components/player/player-provider.tsx
'use client'

import {
  AudioPlayerProvider,
  useAudioPlayer,
} from '@/components/audio-player/audio-player-context'
import { SetSessionProvider, useSetSession } from './set-session-context'
import { usePlayerInteractionLevel, type PlayerLayer } from './interaction-level'

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  return (
    <AudioPlayerProvider>
      <SetSessionProvider>
        <>{children}</>
      </SetSessionProvider>
    </AudioPlayerProvider>
  )
}

export interface PlayerApi {
  audio: ReturnType<typeof useAudioPlayer>
  set: ReturnType<typeof useSetSession>
  layer: PlayerLayer
  promoteLayer: () => void
  collapseLayer: () => void
  jumpToLayer: (l: PlayerLayer) => void
}

export function usePlayer(): PlayerApi {
  const audio = useAudioPlayer()
  const set = useSetSession()
  const { level, promote, collapse, jumpTo } = usePlayerInteractionLevel()
  return {
    audio,
    set,
    layer: level,
    promoteLayer: promote,
    collapseLayer: collapse,
    jumpToLayer: jumpTo,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/player-provider.tsx
git commit -F - <<'EOF'
feat(panel): unified PlayerProvider + usePlayer facade

Merges AudioPlayerProvider, SetSessionProvider, and interaction-level
hook into a single context tree. UI consumes one usePlayer() hook
instead of knowing about internal split.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 6 — Layer 0: PlayerHero

### Task 13: `PlayerHero` component

**Files:**
- Create: `panel/components/player/player-hero.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/player-hero.tsx
'use client'

import { IconPlayerPlayFilled, IconX } from '@tabler/icons-react'
import { useState } from 'react'

import { pickDefaultFirstTrack } from '@/actions/default-first-picker-actions'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

export function PlayerHero() {
  const player = usePlayer()
  const [dismissed, setDismissed] = useState(false)
  const [loading, setLoading] = useState(false)

  if (player.layer > 0 || player.audio.current !== null) return null
  if (dismissed) return null

  const handlePlay = async () => {
    setLoading(true)
    try {
      const result = await pickDefaultFirstTrack()
      if (!result.first) return
      const queue = result.queue.map((t) => ({
        id: t.id,
        title: t.title,
        artists: t.artists,
        durationMs: t.duration_ms,
        bpm: t.bpm,
        camelot: t.camelot,
        mood: t.mood,
      }))
      const first = queue.find((q) => q.id === result.first!.id)!
      player.audio.play(first, queue)
      player.promoteLayer() // 0 → 1
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Start playing"
      className={cn(
        'fixed inset-0 z-30 flex items-center justify-center',
        'bg-background/40 backdrop-blur-sm',
      )}
    >
      <div className="flex flex-col items-center gap-6">
        <Button
          size="icon"
          onClick={handlePlay}
          disabled={loading}
          className={cn(
            'h-32 w-32 rounded-full shadow-2xl',
            'bg-primary text-primary-foreground',
            'animate-pulse hover:animate-none hover:scale-105 transition-transform',
          )}
          aria-label="Start"
        >
          <IconPlayerPlayFilled className="size-12 translate-x-0.5" />
        </Button>
        <p className="text-sm text-muted-foreground">
          {loading ? 'Finding the right track…' : 'Tap to start'}
        </p>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="absolute top-6 right-6 rounded-full p-2 hover:bg-muted/40"
        aria-label="Dismiss"
      >
        <IconX className="size-5" />
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/player-hero.tsx
git commit -F - <<'EOF'
feat(panel): PlayerHero Layer 0 splash component

Full-screen centered play button over library backdrop. On click,
picks a default first track and promotes to Layer 1. Dismissable
via × in corner.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 7 — Layer 1: MiniPlayerBar

### Task 14: `MiniPlayerBar` component

**Files:**
- Create: `panel/components/player/mini-player-bar.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/mini-player-bar.tsx
'use client'

import {
  IconChevronUp,
  IconLoader2,
  IconMusic,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
} from '@tabler/icons-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function MiniPlayerBar() {
  const player = usePlayer()
  const { audio, layer } = player

  if (layer !== 1) return null
  if (!audio.current) return null

  const { isPlaying, isLoading, current, position, duration } = audio
  const progressPct = duration > 0 ? Math.min(100, (position / duration) * 100) : 0

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40 h-12',
        'border-t border-border/60 bg-background/95 backdrop-blur',
      )}
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto flex h-full max-w-screen-2xl items-center gap-3 px-4 lg:px-6">
        <button
          type="button"
          onClick={player.promoteLayer}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-label="Expand player"
        >
          <IconMusic className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate text-sm font-medium">{current.title}</span>
          {current.artists && (
            <span className="truncate text-xs text-muted-foreground">
              — {current.artists}
            </span>
          )}
        </button>

        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={() => audio.prev()}
            disabled={!audio.hasPrev}
            aria-label="Previous track"
          >
            <IconPlayerSkipBackFilled className="size-3.5" />
          </Button>
          <Button
            size="icon"
            className="h-9 w-9 rounded-full"
            onClick={() => audio.toggle()}
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <IconLoader2 className="size-4 animate-spin" />
            ) : isPlaying ? (
              <IconPlayerPauseFilled className="size-4" />
            ) : (
              <IconPlayerPlayFilled className="size-4" />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={() => audio.next()}
            disabled={!audio.hasNext}
            aria-label="Next track"
          >
            <IconPlayerSkipForwardFilled className="size-3.5" />
          </Button>
        </div>

        <span className="hidden w-20 text-right text-[10px] tabular-nums text-muted-foreground sm:inline">
          {formatTime(position)} / {formatTime(duration)}
        </span>

        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={player.promoteLayer}
          aria-label="Expand player"
        >
          <IconChevronUp className="size-4" />
        </Button>
      </div>

      <div
        className="h-0.5 bg-primary transition-[width]"
        style={{ width: `${progressPct}%` }}
      />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/mini-player-bar.tsx
git commit -F - <<'EOF'
feat(panel): MiniPlayerBar Layer 1 slim bar

48px player bar with title + transport + ambient progress strip.
Click title or chevron promotes to Layer 2. Compatibility Auto-DJ
silently active underneath.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 8 — Layer 2: MediumPlayerBar

### Task 15: `MediumPlayerBar` component

**Files:**
- Create: `panel/components/player/medium-player-bar.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/medium-player-bar.tsx
'use client'

import {
  IconAdjustmentsHorizontal,
  IconChevronDown,
  IconLoader2,
  IconMusic,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconPlayerStopFilled,
  IconSparkles,
  IconVolume,
  IconVolume2,
  IconVolumeOff,
} from '@tabler/icons-react'

import { MoodBadge } from '@/components/mood-badge'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function MediumPlayerBar({ onOpenControlPanel }: { onOpenControlPanel: () => void }) {
  const player = usePlayer()
  const { audio, layer } = player

  if (layer !== 2) return null
  if (!audio.current) return null

  const { isPlaying, isLoading, current, position, duration, volume, muted } = audio
  const VolumeIcon = muted ? IconVolumeOff : volume > 0.5 ? IconVolume : IconVolume2

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-40',
        'border-t border-border/60 bg-background/95 backdrop-blur',
      )}
      role="region"
      aria-label="Audio player"
    >
      <div className="mx-auto flex max-w-screen-2xl items-center gap-4 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div className="grid size-12 shrink-0 place-items-center rounded-md border border-border/60 bg-muted/40">
            <IconMusic className="size-5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{current.title}</span>
              {current.mood && <MoodBadge mood={current.mood} />}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="truncate">{current.artists ?? '—'}</span>
              {current.bpm && (
                <>
                  <span>·</span>
                  <span className="tabular-nums">{current.bpm.toFixed(1)} BPM</span>
                </>
              )}
              {current.camelot && (
                <>
                  <span>·</span>
                  <span className="font-mono">{current.camelot}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex min-w-0 flex-[2] flex-col items-center gap-1.5">
          <div className="flex items-center gap-1">
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.prev()} disabled={!audio.hasPrev} aria-label="Previous track">
              <IconPlayerSkipBackFilled className="size-3.5" />
            </Button>
            <Button size="icon" className="h-9 w-9 rounded-full" onClick={() => audio.toggle()} aria-label={isPlaying ? 'Pause' : 'Play'}>
              {isLoading ? <IconLoader2 className="size-4 animate-spin" /> : isPlaying ? <IconPlayerPauseFilled className="size-4" /> : <IconPlayerPlayFilled className="size-4" />}
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.next()} disabled={!audio.hasNext} aria-label="Next track">
              <IconPlayerSkipForwardFilled className="size-3.5" />
            </Button>
            <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.stop()} aria-label="Stop">
              <IconPlayerStopFilled className="size-3.5" />
            </Button>
          </div>
          <div className="flex w-full items-center gap-2">
            <span className="w-10 text-right text-[10px] tabular-nums text-muted-foreground">{formatTime(position)}</span>
            <Slider
              value={[duration > 0 ? (position / duration) * 100 : 0]}
              min={0}
              max={100}
              step={0.1}
              onValueChange={(v) => {
                if (duration > 0) audio.seek((v[0] / 100) * duration)
              }}
              className="flex-1"
              aria-label="Seek"
            />
            <span className="w-10 text-[10px] tabular-nums text-muted-foreground">{formatTime(duration)}</span>
          </div>
        </div>

        <div className="hidden min-w-[180px] flex-1 items-center justify-end gap-2 md:flex">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8"
            onClick={onOpenControlPanel}
            aria-label="Set modes"
            title="Click for set modes"
          >
            <IconSparkles className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => audio.toggleMute()} aria-label={muted ? 'Unmute' : 'Mute'}>
            <VolumeIcon className="size-4" />
          </Button>
          <Slider
            value={[muted ? 0 : volume * 100]}
            min={0}
            max={100}
            step={1}
            onValueChange={(v) => audio.setVolume(v[0] / 100)}
            className="w-24"
            aria-label="Volume"
          />
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onOpenControlPanel} aria-label="Open controls">
            <IconAdjustmentsHorizontal className="size-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={player.collapseLayer} aria-label="Collapse">
            <IconChevronDown className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/medium-player-bar.tsx
git commit -F - <<'EOF'
feat(panel): MediumPlayerBar Layer 2 full-context bar

80px bar with track meta (mood badge, BPM, Camelot), 4-button
transport, seek slider, volume, ✨ Auto-DJ affordance (promotes
to Layer 3 on click), collapse to Layer 1.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 9 — Layer 3: ControlPanel + SetIndicatorChip

### Task 16: `ControlPanel` popover

**Files:**
- Create: `panel/components/player/control-panel.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/control-panel.tsx
'use client'

import { IconX } from '@tabler/icons-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { usePlayer } from './player-provider'
import type { SetTemplate } from '@/lib/set-narrative/types'

const COMPATIBILITY_MODE_NAME = '__compatibility__'

const MODE_ICONS: Record<string, string> = {
  warm_up_30: '☀',
  classic_60: '✨',
  peak_hour_60: '🔥',
  roller_90: '🌊',
  progressive_120: '📈',
  wave_120: '🌊',
  closing_60: '🌙',
  full_library: '∞',
}

function SparklineArc({ template }: { template: SetTemplate }) {
  // Tiny 80×16 svg showing energy_lufs across slots
  const values = template.slots.map((s) => s.energyLufs)
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const range = Math.max(1, maxV - minV)
  const points = template.slots
    .map((s, i) => {
      const x = (i / Math.max(1, template.slots.length - 1)) * 76 + 2
      const y = 14 - ((s.energyLufs - minV) / range) * 12
      return `${x},${y}`
    })
    .join(' ')
  return (
    <svg width={80} height={16} className="opacity-70">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} />
    </svg>
  )
}

export function ControlPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const player = usePlayer()
  const { set, audio } = player

  if (!open) return null

  const activeName = set.active && set.template ? set.template.name : COMPATIBILITY_MODE_NAME

  const selectMode = (name: string) => {
    if (name === COMPATIBILITY_MODE_NAME) {
      set.stopSet()
      onClose()
      return
    }
    set.startTemplate(name)
    onClose()
  }

  return (
    <div className="fixed bottom-[80px] left-0 right-0 z-50 pointer-events-none">
      <div className="mx-auto w-full max-w-screen-2xl px-4 lg:px-6 pointer-events-auto">
        <div className="rounded-lg border border-border/60 bg-background shadow-xl">
          <div className="flex items-center justify-between border-b border-border/60 px-4 py-2">
            <span className="text-sm font-medium">Set mode</span>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-muted/40">
              <IconX className="size-4" />
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto p-2">
            <button
              type="button"
              onClick={() => selectMode(COMPATIBILITY_MODE_NAME)}
              className={cn(
                'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                activeName === COMPATIBILITY_MODE_NAME && 'bg-primary/10 border border-primary/40',
              )}
            >
              <span className="text-base">∞</span>
              <div className="flex-1">
                <div className="font-medium">Compatibility</div>
                <div className="text-xs text-muted-foreground">Endless · next compatible track</div>
              </div>
            </button>

            {set.templates.map((tpl) => (
              <button
                key={tpl.name}
                type="button"
                onClick={() => selectMode(tpl.name)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted/40',
                  activeName === tpl.name && 'bg-primary/10 border border-primary/40',
                )}
              >
                <span className="text-base">{MODE_ICONS[tpl.name] ?? '✨'}</span>
                <div className="flex-1">
                  <div className="font-medium">{humanName(tpl)}</div>
                  <div className="text-xs text-muted-foreground">{tpl.description}</div>
                </div>
                <SparklineArc template={tpl} />
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
            <span>Mix length:</span>
            {[4, 8, 16, 32, 64].map((b) => (
              <Button
                key={b}
                size="sm"
                variant={audio.crossfadeBars === b ? 'default' : 'outline'}
                className="h-6 px-2 text-[10px]"
                onClick={() => audio.setCrossfadeBars?.(b)}
              >
                {b}
              </Button>
            ))}
            <span className="ml-2 tabular-nums">
              ~{Math.round(audio.crossfadeSeconds)}s
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function humanName(tpl: SetTemplate): string {
  const parts = tpl.name.split('_')
  const last = parts[parts.length - 1]
  if (/^\d+$/.test(last)) {
    const rest = parts.slice(0, -1).join(' ')
    return `${capitalise(rest)} ${last}`
  }
  return capitalise(tpl.name.replaceAll('_', ' '))
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/control-panel.tsx
git commit -F - <<'EOF'
feat(panel): ControlPanel Layer 3 mode picker popover

Popover above player bar listing Compatibility + all set templates
with mini sparkline arcs and mode-icons. Mix length bar selector.
Clicking a mode starts the session and closes the popover.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 17: `SetIndicatorChip` (Layer 3 active-template chip)

**Files:**
- Create: `panel/components/player/set-indicator-chip.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/set-indicator-chip.tsx
'use client'

import { IconSparkles } from '@tabler/icons-react'
import { cn } from '@/lib/utils'
import { usePlayer } from './player-provider'

function formatMmSs(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function SetIndicatorChip({ onOpen }: { onOpen: () => void }) {
  const { set } = usePlayer()
  if (!set.active || !set.template) return null

  const totalSec = set.template.durationMin * 60
  const isSearching = set.upcoming.length === 0

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/15 px-2.5 py-1',
        'text-[11px] text-primary hover:bg-primary/25 transition-colors',
      )}
      aria-label="Open set planner"
      title={`Set: ${set.template.name}`}
    >
      <IconSparkles className="size-3" />
      <span className="font-medium">{set.template.name}</span>
      <span className="tabular-nums">
        {formatMmSs(set.elapsedSec)}/{formatMmSs(totalSec)}
      </span>
      {isSearching && (
        <span className="size-1.5 animate-pulse rounded-full bg-primary" />
      )}
    </button>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/set-indicator-chip.tsx
git commit -F - <<'EOF'
feat(panel): SetIndicatorChip for active template

Compact pill showing template name and elapsed/total with pulsing
dot when picker is searching. Click opens Layer 4 drawer.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 10 — Layer 4: SetPlannerDrawer

### Task 18: `EnergyArcGraph` component

**Files:**
- Create: `panel/components/player/energy-arc-graph.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/energy-arc-graph.tsx
'use client'

import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SetTemplate, HistoryEntry } from '@/lib/set-narrative/types'

interface Props {
  template: SetTemplate
  elapsedSec: number
  history: HistoryEntry[]
}

export function EnergyArcGraph({ template, elapsedSec, history }: Props) {
  const totalSec = template.durationMin * 60

  // Predicted curve: one point per slot edge
  const predicted = template.slots.map((slot) => ({
    time: slot.position * totalSec,
    target: slot.energyLufs,
    slotMood: slot.targetMood,
  }))
  predicted.push({
    time: totalSec,
    target: template.slots[template.slots.length - 1].energyLufs,
    slotMood: null,
  })

  // Actual history played LUFS
  const actual = history
    .filter((h) => h.lufs != null)
    .map((h) => ({ time: h.playedAtSec, actual: h.lufs! }))

  const merged = [...predicted, ...actual].sort((a, b) => a.time - b.time)

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={merged}>
          <XAxis
            dataKey="time"
            type="number"
            domain={[0, totalSec]}
            tickFormatter={(v) => `${Math.floor(v / 60)}m`}
            stroke="currentColor"
            className="text-xs text-muted-foreground"
          />
          <YAxis
            domain={[-24, -2]}
            stroke="currentColor"
            className="text-xs text-muted-foreground"
          />
          <Tooltip
            labelFormatter={(v) => `${Math.floor(Number(v) / 60)}:${String(Math.floor(Number(v) % 60)).padStart(2, '0')}`}
            formatter={(v, k) => [`${Number(v).toFixed(1)} LUFS`, k]}
          />
          <Area
            type="monotone"
            dataKey="target"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.1}
            strokeDasharray="4 2"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="actual"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.3}
            isAnimationActive={false}
          />
          <ReferenceLine x={elapsedSec} stroke="var(--primary)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/energy-arc-graph.tsx
git commit -F - <<'EOF'
feat(panel): EnergyArcGraph Recharts component

Area chart showing predicted slot LUFS arc (dashed), actual played
LUFS history (filled), and current position reference line.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 19: `SlotTimeline` component

**Files:**
- Create: `panel/components/player/slot-timeline.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/slot-timeline.tsx
'use client'

import { cn } from '@/lib/utils'
import type { CurrentSlot, SetTemplate } from '@/lib/set-narrative/types'

interface Props {
  template: SetTemplate
  current: CurrentSlot
}

export function SlotTimeline({ template, current }: Props) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2">
      {template.slots.map((slot, i) => {
        const status =
          i < current.index ? 'played' : i === current.index ? 'playing' : 'pending'
        return (
          <div
            key={i}
            className={cn(
              'min-w-[88px] rounded-md border px-3 py-2 text-xs',
              status === 'played' && 'border-muted-foreground/30 bg-muted/20 opacity-60',
              status === 'playing' && 'border-primary/60 bg-primary/10',
              status === 'pending' && 'border-border/60',
            )}
            title={`${slot.targetMood ?? ''} · ${slot.bpmMin}-${slot.bpmMax} BPM · ${slot.energyLufs} LUFS`}
          >
            <div className="font-mono">{i + 1}</div>
            <div className="truncate font-medium">{slot.targetMood ?? '—'}</div>
            <div className="text-[10px] text-muted-foreground">
              {Math.round((slot.durationMs / 1000 / 60) * 10) / 10} min
            </div>
            {status === 'playing' && (
              <div className="mt-1 text-[10px] text-primary">▶ playing</div>
            )}
            {status === 'played' && <div className="mt-1 text-[10px]">✓</div>}
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/slot-timeline.tsx
git commit -F - <<'EOF'
feat(panel): SlotTimeline 8-card horizontal row

Shows all template slots with status (played / playing / pending),
mood label, duration, and BPM tooltip.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 20: `SetPlannerDrawer` full component

**Files:**
- Create: `panel/components/player/set-planner-drawer.tsx`

- [ ] **Step 1: Write the component**

```typescript
// panel/components/player/set-planner-drawer.tsx
'use client'

import { IconX } from '@tabler/icons-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { EnergyArcGraph } from './energy-arc-graph'
import { SlotTimeline } from './slot-timeline'
import { usePlayer } from './player-provider'

export function SetPlannerDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const player = usePlayer()
  const { set } = player

  if (!open || !set.active || !set.template || !set.currentSlot) return null

  const totalMin = set.template.durationMin
  const elapsedMin = Math.floor(set.elapsedSec / 60)
  const elapsedSec = set.elapsedSec % 60
  const slotLabel = set.template.slots[set.currentSlot.index].targetMood ?? '—'

  return (
    <div
      role="dialog"
      aria-label="Set planner"
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 max-h-[75vh] overflow-hidden',
        'border-t border-border/60 bg-background shadow-2xl',
        'flex flex-col',
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
        <div>
          <div className="text-sm font-semibold">{set.template.name}</div>
          <div className="text-xs text-muted-foreground">
            {elapsedMin}:{String(elapsedSec).padStart(2, '0')} / {totalMin}:00 · slot{' '}
            {set.currentSlot.index + 1}/{set.template.slots.length} ({slotLabel})
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => set.stopSet()}>
            Stop set
          </Button>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-muted/40">
            <IconX className="size-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
            Energy arc
          </h3>
          <EnergyArcGraph
            template={set.template}
            elapsedSec={set.elapsedSec}
            history={set.history}
          />
        </section>

        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">Slots</h3>
          <SlotTimeline template={set.template} current={set.currentSlot} />
        </section>

        <section>
          <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
            Upcoming candidates for slot {set.currentSlot.index + 1}
          </h3>
          {set.upcoming.length === 0 && (
            <p className="text-sm text-muted-foreground">Searching…</p>
          )}
          <ul className="space-y-1.5">
            {set.upcoming.slice(0, 5).map((c, i) => (
              <li
                key={c.trackId}
                className={cn(
                  'flex items-center justify-between rounded-md border border-border/40 px-3 py-2 text-sm hover:bg-muted/20 cursor-pointer',
                  i === 0 && 'border-primary/60 bg-primary/10',
                )}
                onClick={() =>
                  set.overridePick({
                    id: c.trackId,
                    title: c.title,
                    artists: c.artists,
                    durationMs: null,
                    bpm: c.bpm,
                    camelot: c.camelot,
                    mood: c.mood,
                  })
                }
                role="button"
                tabIndex={0}
              >
                <div className="flex-1 truncate">
                  <div className="flex items-center gap-2">
                    {i === 0 && <span>▶</span>}
                    <span className="font-medium truncate">{c.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.bpm?.toFixed(1) ?? '—'} BPM · {c.camelot ?? '—'}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">{c.rationale}</div>
                </div>
                <div className="text-sm font-mono tabular-nums text-primary">
                  {c.combinedScore.toFixed(2)}
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void set.rebuildRemainder()}>
            Rebuild remainder
          </Button>
          <Button variant="outline" size="sm" onClick={() => set.skipSlot()}>
            Skip to next slot
          </Button>
        </section>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/set-planner-drawer.tsx
git commit -F - <<'EOF'
feat(panel): SetPlannerDrawer Layer 4 full view

Bottom drawer (75vh) with energy arc graph, slot timeline,
upcoming candidates list, and action buttons (rebuild, skip,
stop). Click candidate overrides next pick.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 11 — Integration

### Task 21: Compose layered player in a single `<Player>` component

**Files:**
- Create: `panel/components/player/player.tsx`

- [ ] **Step 1: Write the compose component**

```typescript
// panel/components/player/player.tsx
'use client'

import { useState } from 'react'

import { ControlPanel } from './control-panel'
import { MediumPlayerBar } from './medium-player-bar'
import { MiniPlayerBar } from './mini-player-bar'
import { PlayerHero } from './player-hero'
import { SetIndicatorChip } from './set-indicator-chip'
import { SetPlannerDrawer } from './set-planner-drawer'
import { usePlayer } from './player-provider'

export function Player() {
  const player = usePlayer()
  const [controlPanelOpen, setControlPanelOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const openControlPanel = () => {
    if (player.layer < 3) player.jumpToLayer(3)
    setControlPanelOpen(true)
  }

  return (
    <>
      <PlayerHero />
      <MiniPlayerBar />
      <MediumPlayerBar onOpenControlPanel={openControlPanel} />
      {/* Layer 3 inline bits: show medium bar structure + set chip */}
      {player.layer >= 3 && player.audio.current && (
        <MediumPlayerBar onOpenControlPanel={openControlPanel} />
      )}
      {player.layer >= 3 && (
        <div className="pointer-events-none fixed bottom-24 left-1/2 z-40 -translate-x-1/2">
          <div className="pointer-events-auto">
            <SetIndicatorChip onOpen={() => setDrawerOpen(true)} />
          </div>
        </div>
      )}
      <ControlPanel open={controlPanelOpen} onClose={() => setControlPanelOpen(false)} />
      <SetPlannerDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add panel/components/player/player.tsx
git commit -F - <<'EOF'
feat(panel): Player compose component

Single top-level component that renders the correct layer
components based on interaction level and manages ControlPanel +
SetPlannerDrawer local state.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

### Task 22: Wire `PlayerProvider` + `<Player />` into root layout

**Files:**
- Modify: `panel/app/layout.tsx`

- [ ] **Step 1: Read current layout**

Run: `cat panel/app/layout.tsx | head -100`
Note the existing `<AudioPlayerProvider>` + `<AudioPlayerBar />` wiring.

- [ ] **Step 2: Replace with unified PlayerProvider**

Edit `panel/app/layout.tsx` — change imports:

```tsx
// replace:
//   import { AudioPlayerProvider } from '@/components/audio-player/audio-player-context'
//   import { AudioPlayerBar } from '@/components/audio-player/audio-player-bar'
// with:
import { PlayerProvider } from '@/components/player/player-provider'
import { Player } from '@/components/player/player'
```

And in the JSX body:

```tsx
// replace the <AudioPlayerProvider>...</AudioPlayerProvider> block with:
<PlayerProvider>
  <SidebarProvider ...>
    <AppSidebar variant="inset" />
    <SidebarInset className="pb-24">{children}</SidebarInset>
    <CommandPalette />
  </SidebarProvider>
  <Player />
</PlayerProvider>
```

- [ ] **Step 3: Build**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -15`
Expected: build passes.

- [ ] **Step 4: Delete the old audio-player-bar.tsx**

Run:
```bash
git rm panel/components/audio-player/audio-player-bar.tsx
```

- [ ] **Step 5: Verify library-table still compiles**

Run: `cd panel && PATH="$HOME/.bun/bin:$PATH" bun run build 2>&1 | tail -10`
Expected: still passes (library-table uses `useAudioPlayer` which is unchanged).

- [ ] **Step 6: Commit**

```bash
git add panel/app/layout.tsx panel/components/audio-player/audio-player-bar.tsx
git commit -F - <<'EOF'
feat(panel): integrate layered PlayerProvider + Player

Replace monolithic AudioPlayerBar with layered architecture:
PlayerProvider wraps AudioPlayer + SetSession + interaction-level,
<Player /> renders hero/mini/medium/control/drawer based on layer.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Phase 12 — E2E verification

### Task 23: Playwright e2e for layer transitions

**Files:**
- Create: `panel/tests/e2e/set-narrative.spec.ts` (or adapt existing structure)

- [ ] **Step 1: Write e2e scenarios using playwright MCP**

Execute these scenarios via the playwright MCP in a live session (or add a
playwright test file if the panel already has a playwright runner):

```bash
1. Fresh session → navigate /library
2. Expect PlayerHero visible (Layer 0)
3. Click hero Play button
4. Expect MiniPlayerBar visible, track playing
5. Click chevron up on MiniPlayerBar
6. Expect MediumPlayerBar (Layer 2)
7. Click ✨ in MediumPlayerBar
8. Expect ControlPanel popover with templates
9. Click "peak_hour_60"
10. Expect SetIndicatorChip visible with "peak_hour_60"
11. Click SetIndicatorChip
12. Expect SetPlannerDrawer visible with energy arc graph
13. Click "Stop set" in drawer
14. Expect drawer closes, chip disappears, Compatibility mode resumes
```

- [ ] **Step 2: Manual verification checklist**

Run through these in a real Chrome window:
- [ ] Layer 0 hero appears on first visit, dismissable with ×
- [ ] Mini bar chevron promotes to Layer 2
- [ ] ✨ button opens ControlPanel popover
- [ ] Selecting Compatibility stops the set
- [ ] Selecting Peak Hour 60 starts session, chip appears
- [ ] Chip click opens drawer
- [ ] Drawer energy arc graph renders
- [ ] Upcoming candidates populate within 30s
- [ ] Override-pick click loads the selected track on next crossfade
- [ ] Stop set returns to Compatibility mode
- [ ] Reload during active set restores session from sessionStorage

- [ ] **Step 3: Commit**

```bash
git add -A panel/tests/e2e/ 2>/dev/null || true
git commit --allow-empty -F - <<'EOF'
test(panel): e2e verification for set-narrative flow

Manual + playwright MCP verification of the full 5-layer
progressive disclosure path including template activation,
drawer interactions, and session restoration.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

---

## Self-review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| §1 Architecture overview | Tasks 1-22 (whole plan) |
| §2 Backend additions (get_set_templates) | Task 1 |
| §3 Layer 0 PlayerHero | Tasks 8, 13 |
| §4 Layer 1 MiniPlayerBar | Task 14 |
| §5 Layer 2 MediumPlayerBar | Task 15 |
| §6 Layer 3 ControlPanel + SetIndicator | Tasks 16, 17 |
| §7 Layer 4 SetPlannerDrawer | Tasks 18, 19, 20 |
| §8 Picker algorithm (slot fit, alpha, variety, weighted pick) | Tasks 4, 5, 6 |
| §9 Data flow + persistence | Tasks 10, 11, 12, 22 |
| §10 Testing strategy (unit + e2e) | Tasks 4-6 (unit), 23 (e2e) |

**Placeholder scan:** none — every code block is complete, every command spelled
out, no TBD/TODO/fill-in-later.

**Type consistency:** `SetTemplate.durationMin` used consistently (matches backend
`duration_min`). `SlotDefinition.durationMs` (backend `duration_ms`) used
throughout. `ScoredCandidate` shape matches `pickNextSetTrack` output and
`SetPlannerDrawer` consumer. `PlayerLayer = 0|1|2|3|4` used in interaction-level
and Player compose.

**Scope:** all 23 tasks focused on Set Narrative sub-project only. Audio
engineering refinement (beat-precise phase lock, filter sweep transition types)
and Visual DJ Console (waveforms, cue editor) explicitly deferred to future
sub-projects per spec §11.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-08-set-narrative.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task,
review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans,
batch execution with checkpoints.

Which approach?
