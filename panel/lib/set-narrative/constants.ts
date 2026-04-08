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
