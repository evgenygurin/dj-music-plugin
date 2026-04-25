'use server'

/**
 * DJ engine mixer/EQ controls — REMOVED in v1.0.
 *
 * The entire `app/engines/` directory (DJ mixing simulator) was deleted in
 * the Phase 7 cutover per the architecture blueprint §13 D15. There is no
 * corresponding MCP tool in v1.0 — the audio engine lives in the browser
 * (Web Audio API, see `panel/components/audio-player/audio-player-context.tsx`).
 *
 * These exports are kept so callers (`panel/app/page.tsx` Layer-0 hero)
 * still compile, but every invocation throws a clear error pointing at
 * the blueprint. UI buttons calling these should be disabled in a follow-up
 * sweep.
 */

export interface MixerState {
  crossfader: number
  channel_gain: Record<number, number>
  eq: Record<number, { low: number; mid: number; high: number }>
  filter: Record<number, number>
}

const DEAD_MESSAGE =
  'mixer engine removed in v1.0; UI buttons calling this should be disabled. ' +
  'See docs/superpowers/specs/2026-04-17-architecture-blueprint-design.md §13 D15.'

export async function setEq(
  _deckId: number,
  _band: string,
  _gain: number
): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}

export async function killEq(_deckId: number, _band: string): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}

export async function resetEq(_deckId: number): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}

export async function setFilter(_deckId: number, _cutoffHz: number): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}

export async function getMixerState(): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}

export async function setCrossfader(_target: number): Promise<MixerState | null> {
  throw new Error(DEAD_MESSAGE)
}
