# Maximal Documentation Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill all gaps in Claude Code rules so Claude makes zero avoidable mistakes in any project area.

**Architecture:** 5 new rule files + 2 panel CLAUDE.md files + 4 updates to existing files. All content is pre-extracted from code and FastMCP docs — no research needed during execution.

**Tech Stack:** Markdown files, YAML frontmatter, `.claude/rules/`, Next.js panel

---

### Task 1: Fix `workflows.md` frontmatter (missing `description:`)

**Files:**
- Modify: `.claude/rules/workflows.md:1-3`

- [ ] **Step 1: Add missing `description:` to frontmatter**

Replace the opening frontmatter:

```markdown
---
description: Workflow orchestration patterns — multi-service coordination per MCP tool call
globs: app/services/workflows/**/*.py
---
```

(Currently has only `globs:` — no `description:` means the rule never surfaces in Claude Code.)

- [ ] **Step 2: Verify**

```bash
head -4 .claude/rules/workflows.md
```
Expected: `description:` on line 2.

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/workflows.md
git commit -m "docs(rules): fix workflows.md missing description frontmatter"
```

---

### Task 2: Create `bootstrap.md`

**Files:**
- Create: `.claude/rules/bootstrap.md`

- [ ] **Step 1: Write the file**

```markdown
---
description: Bootstrap composition root — server assembly, middleware, transforms, lifespans, FileSystemProvider
globs:
  - app/bootstrap/**/*.py
  - app/server.py
---

# Bootstrap

The bootstrap layer wires all server components together. Never add business logic here.

## `server_builder.py` — composition root

Call order is fixed:

```python
mcp = FastMCP(
    providers=[FileSystemProvider(mcp_dir)],     # auto-discovers controllers/
    transforms=build_pre_constructor_transforms(), # ToolTransform before first load
    lifespan=build_server_lifespan(),
    sampling_handler=sampling_handler,
)
register_post_constructor_transforms(mcp)  # PromptsAsTools, ResourcesAsTools
register_middleware(mcp, ...)              # after transforms
apply_visibility_policy(mcp)              # mcp.disable(tags=...) — always last
```

**Order is critical.** Violating it causes invisible bugs (transforms applied to wrong tool set, visibility not honoring middleware, etc.).

## Lifespans

Decorator: `@lifespan` from `fastmcp.server.lifespan`.  
Composition: `|` operator — enter left→right, exit right→left, dicts merged.

```python
return db_lifespan | provider_lifespan | analyzer_lifespan | cache_lifespan
```

| Lifespan | Key(s) yielded |
|----------|---------------|
| `db_lifespan` | `db_engine`, `db_session_factory` |
| `provider_lifespan` | `provider_registry`, `ym_client` |
| `analyzer_lifespan` | `analyzer_registry` |
| `cache_lifespan` | `transition_cache` |

Access in tools: `ctx.lifespan_context["db_engine"]` (via DI helpers, not directly).

**Adding a lifespan**: decorate with `@lifespan`, yield a dict, append `| new_lifespan` in `build_server_lifespan()`. Always `try/finally` for cleanup.

## Middleware Pipeline (ordered, `register_middleware()`)

| # | Middleware | Purpose |
|---|-----------|---------|
| 1 | `ToolCallTimeoutMiddleware` | per-tool timeouts (build_set=120s, analyze_batch=600s) |
| 2 | `StructuredLoggingMiddleware` | JSON structured logs |
| 3 | `DetailedTimingMiddleware` | latency tracking |
| 4 | `ResponseLimitingMiddleware(max_size=50_000)` | truncate giant responses |
| 5 | `ResponseCachingMiddleware` | **currently disabled** (both call_tool + read_resource) |
| 6 | `YMRateLimitMiddleware` | rate-limit YM API tool calls |
| 7 | `ErrorHandlingMiddleware` | structured errors + Sentry callback |
| 8 | `RetryMiddleware(max_retries=2)` | retry transient errors |

To add a new middleware: call `mcp.add_middleware(MyMiddleware(...))` inside `register_middleware()`. First added = outermost layer.

## ToolTransform

`app/bootstrap/transforms.py` — two functions:

**Pre-constructor** (passed to `FastMCP(transforms=...)`):
- One `ToolTransform({name: ToolTransformConfig(...)})` dict
- Rewrite `description` for action-dispatched tools (enumerate all `action` values)
- Hide internal params: `ArgTransformConfig(hide=True, default=10)` for `top_n`, `batch_size`
- Rewrite `data` param description (enumerate shape per action value)

**Post-constructor** (after `mcp` is created):
- `ResourcesAsTools(mcp)` — exposes resources as callable tools
- `PromptsAsTools(mcp)` — exposes prompts as callable tools
- Both wrapped in `try/except ImportError`

## Visibility Policy (`visibility.py`)

```python
_DISABLED_AT_STARTUP = frozenset({"delivery","discovery","curation","sync","ym","audio","memory"})
apply_visibility_policy(mcp)  # calls mcp.disable(tags=_DISABLED_AT_STARTUP)
```

Server-level (all sessions). Users unlock per-session via `unlock_tools(action="unlock", category="...")` → `ctx.enable_components(tags={cat})`.

Adding a hidden category: add tag to `_DISABLED_AT_STARTUP`, tag your tools, update `unlock_tools` help text.

## Sampling (`sampling.py`)

- Set `DJ_ANTHROPIC_API_KEY` to enable server-side sampling fallback
- Without it: LLM client passes `search_queries=[...]` as tool parameters directly
- `behavior="fallback"` — sampling only used if client doesn't provide queries

## FileSystemProvider Auto-Discovery

- Recursively scans `app/controllers/` for `@tool`, `@resource`, `@prompt` decorators
- Tools/resources: no `__init__.py` registration needed
- Prompts: must be in `app/controllers/prompts/workflows/__init__.py` `__all__`

## Gotchas

- `apply_visibility_policy` must run AFTER `register_middleware` — order matters
- Do NOT add transforms after `apply_visibility_policy` — disabled tools won't be transformed
- Lifespan key collisions: later lifespan overwrites earlier. `db_engine`, `db_session_factory` are reserved
- `build_db_session_factory()` adds `statement_cache_size=0` for PostgreSQL only (pgbouncer workaround)
- `on_duplicate="warn"` in FastMCP constructor — duplicate tool names log a warning, not error
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/bootstrap.md
git commit -m "docs(rules): add bootstrap.md — server assembly, middleware, lifespans, transforms"
```

---

### Task 3: Create `transitions.md`

**Files:**
- Create: `.claude/rules/transitions.md`

- [ ] **Step 1: Write the file**

```markdown
---
description: Transition scoring — 6-component formula, Camelot wheel, TransitionIntent
globs:
  - app/transition/**/*.py
  - app/camelot/**/*.py
---

# Transition Scoring

Pure domain logic. No I/O, no DB, no async. All in `app/transition/`.

## TransitionScorer

```python
from app.transition.scorer import TransitionScorer, TransitionScore

scorer = TransitionScorer()  # default weights from settings
score: TransitionScore = scorer.score(from_features, to_features, intent=TransitionIntent.MAINTAIN)
```

Input: two `TrackFeatures` dataclasses. Output: `TransitionScore`.  
`score.hard_reject` must be checked before using `score.total`.

## 6 Components (default weights, sum = 1.0)

Source of truth: `app/core/constants.py:DEFAULT_TRANSITION_WEIGHTS`

| Component | Weight | Key inputs |
|-----------|--------|-----------|
| BPM | 0.20 | `bpm`, `bpm_stability`, `bpm_confidence` |
| Harmonic | 0.12 | `key_code` → `camelot_distance()`, `atonality`, `key_confidence` |
| Energy | 0.18 | `integrated_lufs`, `energy_mean`, `short_term_lufs_mean` |
| Spectral | 0.20 | `spectral_centroid_hz`, `spectral_flatness`, `mfcc_vector` |
| Groove | 0.15 | `onset_rate`, `kick_prominence`, `pulse_clarity` |
| Timbral | 0.15 | `hnr_db`, `chroma_entropy`, `dynamic_complexity` |

## Hard Constraints (gate before scoring)

`check_hard_constraints()` rejects pairs:
- BPM diff > `settings.transition_hard_reject_bpm_diff` → `hard_reject=True`
- Camelot distance ≥ `settings.transition_hard_reject_camelot_dist` → `hard_reject=True`

Always check `score.hard_reject` before using `score.total`.

## Camelot Distance

```python
from app.camelot.wheel import camelot_distance

dist = camelot_distance(from_key_code, to_key_code)  # 0=same, 1=adjacent, 7=max clash
```

`key_code` 0–23: 0–11 = major, 12–23 = minor. Maps to Camelot wheel positions.

## TransitionIntent

```python
from app.transition.types import TransitionIntent     # MAINTAIN, RAMP_UP, COOL_DOWN, CONTRAST
from app.transition.intent import infer_intent, INTENT_WEIGHT_MODIFIERS

intent = infer_intent(set_position=0.3, energy_delta_lufs=1.5, template=SetTemplate.CLASSIC_60)
```

`infer_intent()` auto-detects from position and energy delta. Template shifts phase boundaries.

Weight modifiers per intent (override defaults):
- `MAINTAIN`: BPM 0.28, energy 0.15 (flow)
- `RAMP_UP`: energy 0.30, harmonic 0.25 (build)
- `COOL_DOWN`: energy 0.25, BPM 0.20 (smooth descent)
- `CONTRAST`: spectral 0.20, timbral 0.20 (variety)

## TransitionScore Fields

`total: float`, per-component `bpm/harmonic/energy/spectral/groove/timbral: float`,
`hard_reject: bool`, `reject_reason: str | None`, `soft_conflicts: list[str]`

## Gotchas

- `TransitionScorer` does NOT access DB — requires pre-loaded `TrackFeatures`
- Missing features (None) fall back to neutral score (0.5), not zero — do not pre-filter None features
- `VOCAL_PITCH_SALIENCE_THRESHOLD`: tracks above it get modified timbral scoring (detects vocals in mix)
- `DRUM_ONLY_WEIGHT_OVERRIDE`: short tracks without harmonic content → BPM weight boosted
- `bpm_distance()` from `app/transition/math_helpers` handles half-tempo doubling (e.g. 75 BPM vs 150 BPM = dist 0, not 75)
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/transitions.md
git commit -m "docs(rules): add transitions.md — 6-component scoring, Camelot, TransitionIntent"
```

---

### Task 4: Create `optimization.md`

**Files:**
- Create: `.claude/rules/optimization.md`

- [ ] **Step 1: Write the file**

```markdown
---
description: Set optimization — GA, greedy, fitness, algorithm selection, OptimizerStrategy
globs: app/optimization/**/*.py
---

# Set Optimization

Pure domain logic. No I/O, no DB, no async. All in `app/optimization/`.

## Strategy Pattern

Both algorithms implement `OptimizerStrategy` protocol (`app/optimization/protocol.py`):

```python
class OptimizerStrategy(Protocol):
    def optimize(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
        excluded: set[int] | None = None,
        template: SetTemplateDefinition | None = None,
        moods: dict[int, str | None] | None = None,
        on_progress: Callable[[int, float], None] | None = None,
    ) -> OptimizationResult: ...
```

## Algorithm Selection

| Algorithm | Use when | Complexity |
|-----------|---------|-----------|
| `GreedyChainBuilder` | < 30 tracks, quick preview, rebuild | O(n²), deterministic |
| `GeneticAlgorithm` | ≥ 30 tracks, final set | Stochastic, slower, higher quality |

`BuildSetWorkflow` selects automatically based on track count + `algorithm` param.

## GeneticAlgorithm

```python
from app.optimization.genetic import GeneticAlgorithm

optimizer = GeneticAlgorithm(scorer=TransitionScorer())
result = optimizer.optimize(tracks, track_ids, template=template, on_progress=cb)
```

All params default to `settings.ga_*` — override only in tests:
- `ga_population_size` (50), `ga_max_generations` (100), `ga_mutation_rate` (0.1)
- `ga_elitism_rate` (0.1), `ga_tournament_size` (5), `ga_convergence_threshold` (20)

Uses 2-opt post-processing on best individual after GA convergence.

## GreedyChainBuilder

```python
from app.optimization.greedy import GreedyChainBuilder

optimizer = GreedyChainBuilder(scorer=TransitionScorer())
result = optimizer.optimize(tracks, track_ids, pinned={42})
```

Greedily picks best opening track (low energy, good BPM compatibility), then best next transition.
`pinned` tracks always appear. `excluded` tracks removed unless pinned.

## Fitness (`app/optimization/fitness.py`)

`compute_fitness(sequence, features_map, scorer, template)` → `float` [0, 1]

- Scores all consecutive transitions
- Penalizes hard rejects
- Weights by `TransitionIntent` (via `infer_intent` per position)
- Used by both GA (per-individual) and `OptimizationResult.quality_score`

## Adjacency Pre-filter (`candidate_filter.py`)

`build_adjacency(features_map)` — pre-computes which tracks can follow each track (passes hard constraints). Both algorithms use this to prune search space before optimization.

## OptimizationResult

```python
@dataclass
class OptimizationResult:
    track_order: list[int]  # ordered track IDs
    quality_score: float    # 0–1 fitness
```

## Gotchas

- `excluded` tracks are removed UNLESS also in `pinned` — pinned always win
- Progress callback signature: `on_progress(generation: int, best_score: float)` — called per GA generation
- GA is non-deterministic — same input yields different order each run. Use `greedy` in tests
- `playlist_order` fallback (in `BuildSetWorkflow`): when no features available — bypasses both optimizers
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/optimization.md
git commit -m "docs(rules): add optimization.md — GA, greedy, fitness, OptimizerStrategy"
```

---

### Task 5: Create `providers.md`

**Files:**
- Create: `.claude/rules/providers.md`

- [ ] **Step 1: Write the file**

```markdown
---
description: MusicProvider protocol and registry — multi-platform music integration
globs:
  - app/providers/**/*.py
  - app/clients/**/*.py
---

# MusicProvider

Universal interface for music platform clients. Services and tools NEVER import concrete clients — always depend on `MusicProvider` protocol or `ProviderRegistry`.

## Protocol (`app/providers/protocol.py`)

`@runtime_checkable` Protocol — 15+ async methods grouped as:

```python
from app.providers.protocol import MusicProvider
from app.providers.models import ProviderTrack, ProviderPlaylist, ProviderSearchResults, ProviderAlbum
```

Method groups: `search`, `get_tracks/get_similar/download_track`, `get_album/get_artist_tracks`,
`get_playlist/create_playlist/add_tracks_to_playlist/...`, `get_liked_ids/add_likes/...`, `close`.

## ProviderRegistry

Created in `provider_lifespan`, yielded as `ctx.lifespan_context["provider_registry"]`.

```python
from app.providers.registry import ProviderRegistry

registry.register(adapter, default=True)  # called once in lifespan
provider = registry.default               # default MusicProvider instance
provider = registry.get(Provider.YM)      # by Provider enum
Provider.YM in registry                   # membership check
```

DI injection: `registry: ProviderRegistry = Depends(get_provider_registry)`.

## Adding a New Provider

1. Implement `MusicProvider` protocol in `app/clients/<platform>/adapter.py`
2. Add enum value to `app/core/constants.py:Provider`
3. Register in `provider_lifespan`: `registry.register(adapter, default=False)`
4. `registry.close_all()` calls `adapter.close()` on shutdown — implement it

## Models (`app/providers/models.py`)

- `ProviderTrack` — universal track (id, title, artists, album_id, duration_ms, ym_id, etc.)
- `ProviderPlaylist` — universal playlist (id, title, track_count, visibility)
- `ProviderAlbum` — universal album
- `ProviderSearchResults` — wrapper with `tracks: list[ProviderTrack]`, `total`, `page`

## Gotchas

- `ym_client` key in lifespan context preserved for backward compat — use `provider_registry` in new code
- YM-specific operations (playlist diff array format) stay in `app/clients/ym/` — not in the protocol
- `ProviderRegistry` clears itself on `close_all()` — providers are gone after shutdown
- `provider.provider` property returns the `Provider` enum value — used as registry key
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/providers.md
git commit -m "docs(rules): add providers.md — MusicProvider protocol, registry, multi-platform"
```

---

### Task 6: Create `entities.md`

**Files:**
- Create: `.claude/rules/entities.md`

- [ ] **Step 1: Write the file**

```markdown
---
description: Domain entity dataclasses — TrackFeatures, pure domain layer, no DB/HTTP
globs: app/entities/**/*.py
---

# Domain Entities

Pure dataclasses. No DB, no HTTP, no ORM. In `app/entities/` — importable from any layer without circular dependencies.

## TrackFeatures (`app/entities/audio/features.py`)

Minimal feature set for transition scoring and optimization.

```python
from app.entities.audio.features import TrackFeatures

# From DB row
features = TrackFeatures.from_db(row)      # row = TrackAudioFeaturesComputed ORM instance

# Manual
features = TrackFeatures(bpm=128.0, key_code=5, integrated_lufs=-8.5)
```

All fields are optional (`float | None`, `int | None`, `list[float] | None`, `bool | None`).  
Missing features are safe — scorers handle None with neutral fallback (0.5).

## Field Groups

| Group | Fields |
|-------|--------|
| Core | `bpm`, `key_code`, `integrated_lufs`, `energy_mean`, `onset_rate`, `kick_prominence` |
| Spectral | `spectral_centroid_hz`, `spectral_flatness`, `mfcc_vector` (list), `energy_bands` (6 floats) |
| Groove | `onset_rate`, `kick_prominence`, `pulse_clarity`, `hp_ratio` |
| Timbral | `hnr_db`, `chroma_entropy`, `dynamic_complexity` |
| P3 BPM | `bpm_confidence`, `variable_tempo`, `bpm_histogram_first_peak_weight` |
| P3 Harmonic | `atonality`, `key_confidence` |
| Beatgrid | `first_downbeat_ms` — phase-accurate downbeat position in **milliseconds** from track start |
| Mood | `mood: str | None` — for filtering/reasoning only, NOT used by TransitionScorer |

## `from_db()` Quirks

- `mfcc_vector`, `tonnetz_vector`, `beat_loudness_band_ratio`, `tempogram_ratio_vector`: stored as JSON strings in DB, auto-parsed
- `energy_bands`: assembled from 6 separate columns (`energy_sub`, `energy_low`, `energy_lowmid`, `energy_mid`, `energy_highmid`, `energy_high`)

## Gotchas

- `TrackFeatures` has NO `track_id` field — it's stateless. Callers maintain `id → TrackFeatures` mapping
- `first_downbeat_ms` is in **milliseconds**, not seconds — convert before audio math
- `mood` is NOT used in `TransitionScorer` — higher-level filtering/reasoning only
- Do NOT add DB models or imports to `app/entities/` — pure domain layer only
- `energy_bands` requires ALL 6 band columns to be non-None — returns `None` if any is missing
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/entities.md
git commit -m "docs(rules): add entities.md — TrackFeatures dataclass, field groups, from_db quirks"
```

---

### Task 7: Fill `panel/app/CLAUDE.md`

**Files:**
- Modify: `panel/app/CLAUDE.md` (replace claude-mem stub with real rules)

- [ ] **Step 1: Write the file**

Preserve any existing `<claude-mem-context>` block at the bottom. Write rules before it:

```markdown
# App Router Rules (Next.js 16)

## Page Structure

Every route follows this pattern:
```
panel/app/<route>/
├── page.tsx        # Server component — async, fetches data directly from Supabase
├── loading.tsx     # Skeleton placeholder (Suspense boundary)
├── error.tsx       # Error boundary — must be 'use client'
```javascript

- `page.tsx` — default server component, `async function`, no `'use client'`
- `loading.tsx` — import `*Skeleton` from `@/components/skeletons`
- `error.tsx` — `'use client'`, use `PageError` from `@/components/page-error`

## Server vs Client Components

- **Default: server component** — async, no `'use client'`
- **Client component** (`'use client'`): required for state, effects, event handlers, `useAudioPlayer`
- Do NOT make a component client just because it uses shadcn — shadcn works server-side

## Data Fetching Pattern

```typescript
// page.tsx (server component)
import { getTracks } from '@/lib/queries/tracks'

export default async function TracksPage() {
  const tracks = await getTracks()
  return <TracksTable tracks={tracks} />
}
```

Data fetching always in server component. Never fetch in client components.

## Server Actions (Mutations)

```typescript
// actions/my-action.ts
'use server'
import { mcpCall } from '@/lib/mcp-client'

export async function myAction(args: Record<string, unknown>) {
  return mcpCall('tool_name', args)
}
```

All mutations → `mcpCall()` → REST API → MCP server → DB. Never write to Supabase directly from panel.

## Fonts (4 variables from root layout)

- `--font-geist-sans` — body (local Geist)
- `--font-geist-mono` — monospace (local Geist Mono)
- `--font-instrument-serif` — display headings
- `--font-jetbrains-mono` — DJ data (BPM, time, counters)

Use `className="dj-data"` for DJ numeric data (applies JetBrains Mono).

## Navigation

- `<Link href="/path">` for navigation (never `<a>`)
- Active state: `usePathname()` from `next/navigation` (client component only)

## Global Layout Providers (from `layout.tsx`)

- `PlayerProvider` — Web Audio engine context, wraps everything
- `SidebarProvider` + `AppSidebar` — desktop sidebar (`hidden md:contents`)
- `BottomNav` — mobile bottom navigation
- `CommandPalette` — Cmd+K search

## Gotchas

- `SidebarInset` has bottom padding `pb-[calc(8.5rem+env(safe-area-inset-bottom,0px))]` — don't add your own
- `<html>` has `className="dark"` and `suppressHydrationWarning` — don't remove either
- `safe-top` / `safe-bottom` utilities: use on mobile full-screen pages for notch/home bar insets
- Metadata export (`export const metadata: Metadata = {...}`) only in server components or `layout.tsx`
```text

- [ ] **Step 2: Commit**

```bash
git add panel/app/CLAUDE.md
git commit -m "docs(panel): add App Router rules to panel/app/CLAUDE.md"
```

---

### Task 8: Fill `panel/components/CLAUDE.md`

**Files:**
- Modify: `panel/components/CLAUDE.md` (replace claude-mem stub with real rules)

- [ ] **Step 1: Write the file**

```markdown
# Component Patterns

## Directory Layout

```
panel/components/
├── ui/                        # shadcn/ui primitives — do NOT edit directly
├── charts/                    # Recharts visualizations (BpmDistribution, KeyDistribution, etc.)
├── audio-player/              # Web Audio engine — see audio-player/CLAUDE.md
├── player/                    # Player UI (TrackWaveform, TransitionVisualizer, etc.)
├── page-shell.tsx             # Standard page wrapper with title + optional action slot
├── page-error.tsx             # Error boundary UI (used in error.tsx files)
├── skeletons.tsx              # Loading skeletons for all pages
├── data-table.tsx             # TanStack Table v8 generic table
├── mood-badge.tsx             # Colored badge for mood classification
├── track-features.tsx         # Feature display card
└── ...                        # Other domain components
```javascript

## Page Composition Pattern

```tsx
// In page.tsx (server component)
import { PageShell } from '@/components/page-shell'

export default async function MyPage() {
  return (
    <PageShell title="Library" action={<ActionButton />}>
      <MyContent />
    </PageShell>
  )
}
```

## Error Boundary (`error.tsx`)

```tsx
'use client'
import { PageError } from '@/components/page-error'

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return <PageError error={error} onReset={reset} />
}
```

## Skeletons (`loading.tsx`)

```tsx
import { LibrarySkeleton } from '@/components/skeletons'
export default function Loading() { return <LibrarySkeleton /> }
```

Each page has a matching skeleton variant in `skeletons.tsx`.

## shadcn/ui

- **Install**: `bunx shadcn@latest add <component>` — adds to `components/ui/`
- **Never edit** `components/ui/` — re-run add to update
- **Icons**: use `@tabler/icons-react` (NOT lucide) for custom icons
  - Exception: shadcn internal icons use lucide — leave them as-is

## Cyberpunk Theme Tokens

Dark mode only. Key CSS variables:
- `--primary` — magenta (`oklch(0.7 0.25 320)`)
- `--chart-1` through `--chart-5` — neon: magenta, cyan, green, yellow, purple

Charts use `fill="var(--chart-N)"` or Recharts `stroke="var(--chart-N)"`.

## `dj-data` CSS Class

Custom utility (JetBrains Mono + tight tracking). Use on all DJ numeric data:
```tsx
<span className="dj-data text-[12px]">{bpm}</span>
```

Apply to: BPM values, LUFS meters, time displays, counters, status codes.

## Data Table

```tsx
import { DataTable } from '@/components/data-table'

<DataTable columns={columns} data={rows} />
```

Uses TanStack Table v8 (`useReactTable`). Always a client component.

## Charts (Recharts)

5 chart components in `components/charts/`:
- `BpmDistributionChart`, `KeyDistributionChart`, `EnergyHeatmap`, `SubgenreChart`, `MoodChart`
- All client components with `'use client'`
- Gradients defined via `<defs><linearGradient>` inside `<AreaChart>`/`<BarChart>`

## Gotchas

- `audio-player-context.tsx` is ~2000 LOC with dual-deck Web Audio engine — read `audio-player/CLAUDE.md` before touching it
- `player-provider.tsx` wraps the context for React context injection — components use `useAudioPlayer()` hook
- Fast Refresh: `audio-player-context.tsx` exports both components AND hooks — types must live in `audio-player-types.ts` or Fast Refresh triggers full reload
- `data-table.tsx` is generic — `columns` prop must match TanStack `ColumnDef<T>[]` type
- `app-sidebar.tsx` uses `offcanvas` collapsible behavior (not `icon` mode)
```text

- [ ] **Step 2: Commit**

```bash
git add panel/components/CLAUDE.md
git commit -m "docs(panel): add component pattern rules to panel/components/CLAUDE.md"
```

---

### Task 9: Update `tools.md` — progress reporting + sampling

**Files:**
- Modify: `.claude/rules/tools.md`

- [ ] **Step 1: Add progress reporting and sampling sections**

Add after the "Context logging" bullet (line ~25):

```markdown
- **Progress reporting**: `await ctx.report_progress(progress=i, total=n)` for long operations. Call at checkpoints during loops. `progress` / `total` can be any unit (items, percentage, bytes). `total` is optional (indeterminate). No effect if client didn't send a progress token.
- **Sampling** (`ctx.sample()`): server-initiated LLM call. Only used by reasoning tools. Requires `DJ_ANTHROPIC_API_KEY` (fallback mode) or client support. Use `search_queries: list[str]` parameter pattern instead when client drives the LLM.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/tools.md
git commit -m "docs(rules): add progress reporting and sampling patterns to tools.md"
```

---

### Task 10: Update `tests.md` — inline-snapshot, dirty-equals

**Files:**
- Modify: `.claude/rules/tests.md`

- [ ] **Step 1: Add testing patterns**

Add before "## Gotchas" section:

```markdown
- **inline-snapshot** (`pytest-inline-snapshot`): for snapshot testing tool results without separate fixture files:
  ```python
  from inline_snapshot import snapshot
  assert result.content[0].text == snapshot("expected text here")
  # First run with --snapshot-update generates the expected value
  ```
- **dirty-equals** for flexible assertions:
  ```python
  from dirty_equals import IsStr, IsInt, HasLen
  assert result.data.track_id == IsInt()
  assert result.data.title == IsStr(min_length=1)
  ```
- **Progress testing**: tools with `ctx.report_progress()` — use `Client(mcp)` in-memory; progress calls are no-ops when no progress token. Test behavior, not progress events.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/tests.md
git commit -m "docs(rules): add inline-snapshot, dirty-equals, progress testing patterns"
```

---

### Task 11: Update `gotchas.md` — lifespan and lifespan context gotchas

**Files:**
- Modify: `.claude/rules/gotchas.md`

- [ ] **Step 1: Add lifespan gotchas**

Append at end of file:

```markdown
## Lifespan context key collisions

`db_lifespan | provider_lifespan | ...` merges yielded dicts left→right. Later lifespans overwrite earlier on key conflict. Reserved keys: `db_engine`, `db_session_factory`, `provider_registry`, `ym_client`, `analyzer_registry`, `transition_cache`. Use unique keys for new lifespans.

## `@asynccontextmanager` lifespans can't use `|`

Legacy `@asynccontextmanager` lifespans aren't composable with `|`. Wrap with `ContextManagerLifespan` from `fastmcp.server.lifespan`:
```python
from fastmcp.server.lifespan import ContextManagerLifespan
combined = ContextManagerLifespan(legacy_lifespan) | new_lifespan
```

## `FileSystemProvider` scans at construction

Tool/resource/prompt discovery happens when `FastMCP(providers=[FileSystemProvider(...)])` is called. Adding a new `@tool` file after construction does nothing — restart the server.
```text

- [ ] **Step 2: Commit**

```bash
git add .claude/rules/gotchas.md
git commit -m "docs(rules): add lifespan collision, asynccontextmanager, FileSystemProvider gotchas"
```

---

### Task 12: Final push

- [ ] **Push all commits**

```bash
git push
```

- [ ] **Verify all rule files have valid frontmatter**

```bash
for f in .claude/rules/*.md; do
  echo "=== $f ==="
  head -5 "$f"
  echo
done
```

Expected: every file has `---`, `description:`, `---`.

---

## Self-Review

**Spec coverage check:**
- [x] `bootstrap.md` — Task 2
- [x] `transitions.md` — Task 3
- [x] `optimization.md` — Task 4
- [x] `providers.md` — Task 5
- [x] `entities.md` — Task 6
- [x] `panel/app/CLAUDE.md` — Task 7
- [x] `panel/components/CLAUDE.md` — Task 8
- [x] `tools.md` updates — Task 9
- [x] `tests.md` updates — Task 10
- [x] `gotchas.md` updates — Task 11
- [x] `workflows.md` fix — Task 1

**No placeholders found. No TBD sections.**
