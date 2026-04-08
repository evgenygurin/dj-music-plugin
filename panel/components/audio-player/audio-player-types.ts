/**
 * Type-only module for the audio player.
 *
 * Lives in a separate file from `audio-player-context.tsx` so that
 * Fast Refresh works cleanly. Mixing type exports with React
 * component / hook exports in a single module forces Next.js to
 * perform a full page reload on every edit (see
 * https://nextjs.org/docs/messages/fast-refresh-reload).
 *
 * Import these from `@/components/audio-player/audio-player-types`
 * or re-export through the context module for convenience.
 */

export interface PlayerTrackMeta {
  id: number
  title: string
  artists?: string | null
  durationMs?: number | null
  bpm?: number | null
  camelot?: string | null
  mood?: string | null
}

/**
 * Manual transition-style override.
 *
 * `'auto'` defers to the backend `score_transitions` recommendation.
 * The four concrete values force a specific runtime style regardless
 * of what the scorer picked, letting the DJ test / override styles
 * by ear via the chip group in MediumPlayerBar.
 *
 * See `startCrossfade` in `audio-player-context.tsx` for the
 * dispatcher that consumes this value.
 */
export type ManualTransitionStyle = 'auto' | 'cut' | 'swap' | 'harmonic' | 'fade'
