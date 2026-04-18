# Set Narrative & Curation Intelligence — Design Spec

**Date**: 2026-04-08
**Status**: Draft → awaiting user review
**Sub-project**: 1 of 3 (Set Narrative → Audio Engineering → Visual Console)

## Goal

Transform Auto-DJ from "next compatible track" into an adaptive set builder that follows
DJ-set narrative templates (warm-up → peak → release) while maintaining track-to-track
compatibility. The whole experience lives inside a single player with **5 layers of
progressive disclosure** (0 → 4) so a first-time visitor can hit Play and get a perfect
set, while a power user can drill into a full set planner with energy arc visualization
and manual override.

## Locked decisions

| Question | Decision | Rationale |
|---|---|---|
| Pre-built vs adaptive picker | **Adaptive** (per-step, not full GA build) | Reactive to user skips, simpler mental model |
| Set lifecycle | **Mode dropdown in player** (Compatibility / Warm-up 30 / Classic 60 / Peak 60 / Roller 90 / Progressive 120 / Wave 120 / Closing 60) | One-click start, no extra dialogs |
| Compatibility vs slot fit | **Weighted combined**, dynamic α (0.6 default, 0.3-0.4 near key slots) | Mirrors real DJ behavior |
| Track pool | **Library + audit filter** | Pre-filtered to "broadcast-quality" techno |
| Variety constraints | **Soft penalties (Tier B)** with auto-relax tier system path to hard rejects | Won't deadlock when pool is thin |
| UI placement | **5-layer progressive disclosure inside player** (no separate `/set-planner` page) | Matches "from Play button to mastery" UX philosophy |

Pool source itself (library / playlist / explicit crate / filtered) is its own future
sub-project. v1 default = library + audit filter.

---

## 1. Architecture overview

### High-level flow

```text
User → Player Hero (Layer 0) → click ▶
  ↓
Smart default picker → first track (top of audit-filtered library)
  ↓
Layer 1 mini bar appears, music plays, Compatibility Auto-DJ silently active
  ↓
User explores → expands to Layer 2 (more controls visible)
  ↓
User clicks ✨ → Layer 3 popover with templates → picks Peak 60
  ↓
SetSession activates: {template, elapsedSec, currentSlot, history}
  ↓
At each crossfade trigger (outroStart): pickNextSetTrack(...) →
  combined scoring → weighted random from top-8 → startCrossfade
  ↓
User clicks set indicator → Layer 4 drawer opens (energy arc, slot timeline,
  upcoming candidates with rationale, manual override)
  ↓
Set ends naturally OR user stops → returns to Compatibility mode
```

### Components

| Component | Layer | Type | Purpose |
|---|---|---|---|
| `<PlayerHero>` | 0 | overlay | Splash invite to start playback |
| `<MiniPlayerBar>` | 1 | fixed bottom | Track + transport + progress |
| `<MediumPlayerBar>` | 2 | fixed bottom | + meta, seek, volume, ✨ icon |
| `<ControlPanel>` | 3 | popover | Mode picker, mix length, settings |
| `<SetIndicatorChip>` | 3 | inline in bar | Active template + elapsed/total |
| `<SetPlannerDrawer>` | 4 | bottom drawer | Energy arc, slots, upcoming, history |
| `<PlayerProvider>` | — | context | Combines AudioPlayer + SetSession |
| `<SetSessionProvider>` | — | context | Active template state, picker logic |

### Layer state machine

```text
Layer 0 (Stillness)
   │ click Play / dismiss×
   ▼
Layer 1 (Music) ◄──────┐
   │ click ▲           │
   ▼                   │
Layer 2 (Awareness) ◄──┤
   │ click ✨ / ⚙      │
   ▼                   │
Layer 3 (Control) ◄────┤
   │ click set chip    │
   ▼                   │
Layer 4 (Mastery)──────┘
   ↑ collapse to previous layer at any time
```

State persisted to `localStorage` as `dj-player-level` so power users skip layers.
Music never stops on layer change.

---

## 2. Backend additions

### 2.1 New MCP tool: `get_set_templates`

Read-only tool exposing the 8 templates from `app/services/optimizer/templates.py`
to clients. Returns JSON with full slot definitions (position, target_mood, energy_lufs,
bpm range, duration, flexibility).

```python
@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
async def get_set_templates() -> dict[str, Any]:
    from app.services.optimizer.templates import get_all_templates
    return {
        "templates": [
            {
                "name": tpl.name,
                "duration_sec": tpl.duration_sec,
                "description": tpl.description,
                "slots": [
                    {
                        "position": slot.position,
                        "target_mood": slot.target_mood,
                        "energy_lufs": slot.energy_lufs,
                        "bpm_min": slot.bpm_min,
                        "bpm_max": slot.bpm_max,
                        "duration_sec": slot.duration_sec,
                        "flexibility": slot.flexibility,
                    }
                    for slot in tpl.slots
                ],
            }
            for tpl in get_all_templates()
        ]
    }
```

Cached client-side on first fetch. ~5KB total payload.

### 2.2 No new tables, no new Python services

Reuses existing `score_transitions`, `audit_playlist`, `filter_tracks`,
`get_library_stats`, `get_track_features`. Only the templates exposure is new.

### 2.3 New panel server actions

| Action | Calls | Purpose |
|---|---|---|
| `fetchSetTemplates()` | `get_set_templates` | Cached templates for client picker |
| `pickNextSetTrack(input)` | `score_transitions` + `filter_tracks` + features batch | Composite picker (slot fit + transition + variety) |
| `fetchAuditedPool(filters)` | `audit_playlist` + `filter_tracks` | Filtered candidate pool for active set |

`pickNextSetTrack` runs server-side (Node) so all backend calls happen in one
round-trip from the browser's perspective. Python backend stays untouched beyond
the templates tool.

---

## 3. Layer 0 — Stillness (`PlayerHero`)

**Triggers**: `playerInteractionLevel === 0 && current === null`

**Visuals**: Centered 120px circular Play button, primary color, drop shadow,
subtle pulse animation. Subtitle "Tap to start". Backdrop `backdrop-blur-sm
bg-background/40` so library content shows through.

**Behaviors**:
- Click Play → run `defaultFirstPicker()` → play first track → animate hero out
  (slide up + fade) → reveal Layer 1
- Click `×` → dismiss hero, stay on Layer 0 without overlay; re-open via
  sidebar `▶` icon

**Default first picker algorithm**:
1. Fetch audit-passed tracks with `analysis_level >= 4 AND mood IS NOT NULL`
2. Sort by `mood_confidence DESC`, take top 50
3. Pick random from top 50
4. Use the same 50 as initial queue for Compatibility Auto-DJ
5. Fallback if empty: any track with `bpm IS NOT NULL`
6. Fallback if no tracks: error toast, hero stays

---

## 4. Layer 1 — Music (`MiniPlayerBar`)

**Height**: 48px. **Position**: `fixed bottom-0 left-0 right-0`.

**Layout**:
```text
[♪] Track Title — Artist Name      [⏮ ⏯ ⏭]      0:23 / 5:24    [▲]
```

**Sub-elements**:
- Note icon + truncated title + artist (max 280px)
- Three transport buttons (prev/play-pause/next) — 36px each
- Read-only position/duration text
- `▲` chevron handle (24px ghost button) — affordance to Layer 2
- 2px primary-color progress strip along the bottom (ambient indicator)

**Hidden in this layer**: volume, mix length, Auto-DJ toggle, mood/BPM/key, stop, mute.

**Behaviors**:
- Click track title or `▲` → promote to Layer 2
- Mouse wheel up over bar → promote to Layer 2 (gesture discovery)
- Transport buttons work — Compatibility Auto-DJ silently active

---

## 5. Layer 2 — Awareness (`MediumPlayerBar`)

**Height**: 80px (animated transition from 48 ~200ms ease-out).

**Layout**:
```text
[♪] Track Title              [⏮ ⏯ ⏭ ⏹]      [✨] [♪] ───●  [⚙][^]
    Artist · Mood · 124 BPM · 8A  ━━━━━●─────  ↑ Auto-DJ
```

**Adds vs Layer 1**:
- Track meta line (artist, MoodBadge, BPM, Camelot)
- Seek slider (drag for seek)
- Stop button ⏹
- Volume control (icon + 80px slider)
- Auto-DJ button ✨ (visible, click → promote Layer 3)
- ⚙ icon for promote Layer 3 (alternative)
- `▲` becomes collapse-to-Layer-1

**Hidden in this layer**: mode picker (visible icon only), mix length selector, set
indicator (no template active yet).

**Discovery hints**:
- After 5 min in Layer 1: tooltip over `▲`: "Подробнее ↑" (once per session)
- Hovering ✨ in Layer 2 for 2s: "Set narratives — click ✨"

---

## 6. Layer 3 — Control (`ControlPanel` popover)

**Trigger**: click ✨ or ⚙ in Layer 2.

**Popover layout** (full-width over MediumPlayerBar, 280px height):
- Title "Set mode" + close ×
- 8 mode rows: radio + name + description + mini sparkline arc (80×16px svg)
- Current selection: primary border + filled radio
- Mix length picker: chips `[4][8][16][32•][64] bars` + computed seconds at current BPM
- Mode visual variants: each template gets a tiny icon (∞, ☀, 🔥, 🌊, 📈, 🌙) for
  emotional differentiation

**Bar in Layer 3** (when template active):
```text
[♪] Title   [⏮ ⏯ ⏭ ⏹]   ●━━━━●─────  [✨ Peak 60 · 0:23/1:00] [♪]──●  [⚙][^]
```

**Set indicator chip**:
- Replaces lone ✨ icon when template active
- `[✨ Peak 60 · 0:23/1:00]` with `bg-primary/15 border-primary/40`
- Pulsing dot when picker is searching for next track (during transition zone)
- Click → promote Layer 4

**Subtle slot energy arc**: 200×8px sparkline as chip background showing whole set
with current position vertical line. Read-only.

**Behaviors**:
- Click `[×]` in popover → close popover, stay in Layer 3
- Click outside → same
- Click set chip → promote Layer 4
- Click `[^]` → collapse Layer 2 (template stays active!)
- Esc → close popover only

---

## 7. Layer 4 — Mastery (`SetPlannerDrawer`)

**Trigger**: click set indicator chip in Layer 3 (only when template is active).

**Layout**: bottom drawer 75vh, slides up over library.

**Sections**:

### 7.1 Header
```text
Peak Hour 60 · 0:23 / 1:00 · slot 4/8 (peak)        [Stop set] [×]
```

### 7.2 Energy Arc Graph (Recharts)
- X axis: time elapsed (0 → duration)
- Y axis: LUFS target
- Three layers:
  - **Played history**: solid primary line (actual LUFS over time)
  - **Now**: pulsing vertical marker
  - **Predicted**: dashed line forward (template slot LUFS targets)

### 7.3 Slot Timeline
- 8 horizontal cards, current highlighted with primary border
- Card content: index, mood label, status (✓ played / ▶ playing / pending), duration
- Click card → expand to show tracks that played in that slot + their scores
- Tooltip with full slot params (BPM range, target LUFS, flexibility)

### 7.4 Upcoming Candidates
- Top 5 from `pickNextSetTrack`, refresh every 30 seconds
- First in list highlighted with `▶`
- Each shows: title, artist, BPM, Camelot, combined score
- Sub-line: rationale breakdown (slot fit, transition, variety)
- Click any → manual override (force this track as next)

### 7.5 Action buttons
- **Override pick** → search picker dialog, choose any track from library
- **Skip to next slot** → forces immediate transition to first track of next slot
- **Rebuild remainder** → re-runs picker for all remaining slots, replaces upcoming
- **Stop set** → terminates session, returns to Compatibility mode

### 7.6 Set History sub-tab
- List of last 20 sessions
- Each: template name, date, duration, avg score, hard conflicts count, "% completed"
- Click → expanded view with track-by-track replay

**Drawer behavior**: scrollable, click `[×]` / Esc / backdrop → collapse to Layer 3.

---

## 8. Picker algorithm

### 8.1 Slot resolution

```ts
function getCurrentSlot(template, elapsedSec): {
  slot, index, positionInSlot, positionInSet
} {
  const positionInSet = elapsedSec / template.durationSec
  for (let i = 0; i < template.slots.length; i++) {
    const slot = template.slots[i]
    const next = template.slots[i + 1]
    const slotStart = slot.position
    const slotEnd = next ? next.position : 1.0
    if (positionInSet >= slotStart && positionInSet < slotEnd) {
      return { slot, index: i,
        positionInSlot: (positionInSet - slotStart) / (slotEnd - slotStart),
        positionInSet }
    }
  }
  return { slot: lastSlot, index: lastIndex, positionInSlot: 1, positionInSet: 1 }
}
```

### 8.2 Slot fit scoring

`slot_fit ∈ [0, 1]` per candidate:

- **BPM gaussian** (50% weight): inside slot range = 1.0 minus small linear penalty;
  outside = gaussian fall-off with σ=4 BPM
- **LUFS gaussian** (30% weight): σ=3 LUFS around `slot.energy_lufs`
- **Mood match** (20% weight): exact = 1.0, energy-neighbor = 0.75, otherwise 0.5
  (uses 15-subgenre energy ordering from `app/core/constants.py`)

### 8.3 Dynamic alpha

```ts
function getAlpha(slot, slotPosition): number {
  let alpha = 0.6  // compatibility-leaning default
  const isKeySlot = ['peak_time', 'industrial', 'hard_techno'].includes(slot.targetMood)
  if (isKeySlot) alpha = 0.4
  if (slotPosition > 0.8) alpha = Math.min(alpha, 0.3)  // ending current slot
  return alpha
}
```

### 8.4 Variety penalties (Tier B with auto-relax to Tier A path)

| Tier | Hard rejects | Soft penalties |
|---|---|---|
| 0 (strictest) | same artist, recently played (last 50) | mood streak |
| 1 (relaxed) | recently played (last 50) | mood streak, same artist |
| 2 (open) | none | all of the above |

Auto-relax: try Tier 0 first → if filtered pool empty → try Tier 1 → still empty
→ Tier 2. Log "constraints relaxed" event so UI can surface it in upcoming list.

Soft penalty multipliers:
- Same artist as previous: ×0.7
- Same mood 3-in-a-row: ×0.8
- Recently played in last 30: ×0.5

### 8.5 Combined score

```ts
combined = (alpha * transition_score + (1 - alpha) * slot_fit) * variety_penalty
```

### 8.6 Weighted random from top-8

```ts
function weightedRandomPick(scored): ScoredCandidate {
  const top = scored.slice(0, 8)
  const total = top.reduce((acc, c) => acc + c.combinedScore, 0)
  let r = Math.random() * total
  for (const c of top) {
    r -= c.combinedScore
    if (r <= 0) return c
  }
  return top[0]
}
```

---

## 9. Data flow & state architecture

```text
<PlayerProvider>
├─ <AudioPlayerProvider>      Web Audio engine, crossfade, playerInteractionLevel
└─ <SetSessionProvider>       Active template, elapsedSec, currentSlot, history,
                              picker, upcoming candidates
                              ↑
                              Subscribes to AudioPlayer's `position`, triggers
                              picker on outroStart, calls play() to inject next
```

UI components consume a single `usePlayer()` hook that merges both providers'
APIs. The internal split is invisible to UI, making future refactors safe.

### State persistence

| State | Storage | Lifetime |
|---|---|---|
| `current`, `queue`, `position` | AudioPlayerProvider | session |
| `playerInteractionLevel` | localStorage | persistent |
| `setSession` | SetSessionProvider + sessionStorage | session (resume on reload) |
| `dismissedHints` | localStorage | persistent |
| `volume`, `crossfadeBars`, `varietyTier` | localStorage | persistent |

---

## 10. Testing strategy

### Unit (Vitest)
- `slotFitScore` — fixture tracks × slot templates → expected scores
- `getAlpha` — boundary conditions (slot start/end, key slots)
- `varietyPenalty` — history fixtures → multipliers
- `weightedRandomPick` — statistical: 1000 runs distribute proportionally
- `getCurrentSlot` — edge cases (elapsed=0, =duration, beyond)

### Integration
- `pickNextSetTrack` server action — mock backend calls, verify orchestration
- `SetSessionProvider` — fake position updates, verify slot transitions

### E2E (Playwright)
- Layer 0 → click Play → Layer 1 transition
- Layer 1 → expand → Layer 2 → ✨ → Layer 3 popover
- Pick Peak 60 → set indicator appears → Layer 4 drawer opens
- Skip 5 tracks → variety penalty visible in upcoming
- Stop set → returns to Compatibility mode

### Regression
- Existing crossfade / bass swap / tempo match tests must still pass
- Library navigation/pagination unchanged
- Auto-DJ Compatibility mode (existing) must still work

---

## 11. Out of scope (deferred to sub-projects 2 & 3)

- Beat-precise phase lock (sub-project 2)
- Filter sweep / echo tail / hard drop transition styles (sub-project 2)
- Tempo blend mode (sub-project 2)
- Waveform visualization (sub-project 3)
- Cue point editor (sub-project 3)
- Headphone cue split routing (sub-project 3)
- Pool selection UI (its own future sub-project — for v1, audit-filtered library
  is the only pool)
- Full GA pre-build of sets (this is "adaptive", not "rails")
- Backend changes beyond exposing templates

---

## 12. Open questions

None remaining as of writing. All design decisions locked through brainstorming.
