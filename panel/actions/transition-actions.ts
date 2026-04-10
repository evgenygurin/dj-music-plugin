'use server'

import { callTool } from '@/lib/mcp-client'
import { createClient } from '@/lib/supabase/server'

export interface TransitionCandidate {
  to_track_id: number
  overall_quality: number
  bpm_distance: number | null
  energy_step: number | null
  groove_similarity: number | null
  key_distance_weighted: number | null
  title?: string
  artists?: string | null
  duration_ms?: number | null
  bpm?: number | null
  camelot?: string | null
  mood?: string | null
}

/** 6 transition styles surfaced from the backend `recommend_style` decision. */
export type TransitionStyle =
  | 'cut'
  | 'bass_swap_short'
  | 'bass_swap_long'
  | 'long_blend'
  | 'echo_out'
  | 'filter_sweep'

/** Pair-score response with the recommended style + bars for the audio engine. */
export interface PairScoreResult {
  fromTrackId: number
  toTrackId: number
  overall: number | null
  hardReject: boolean
  rejectReason: string | null
  recommendedStyle: TransitionStyle | null
  recommendedBars: number | null
}

/**
 * Asks the backend's TransitionScorer for the best matching next tracks.
 * Returns null when scoring is unavailable (track lacks audio features) so
 * the caller can fall back to the lightweight client-side heuristic.
 */
export async function scoreTransitionCandidates(
  fromTrackId: number,
  topN: number = 20,
): Promise<TransitionCandidate[] | null> {
  try {
    const result = await callTool('score_transitions', {
      mode: 'track_candidates',
      track_id: fromTrackId,
      top_n: topN,
    })
    const sc = result?.structured_content as
      | { candidates?: TransitionCandidate[]; transitions?: TransitionCandidate[] }
      | undefined
    const list = sc?.candidates ?? sc?.transitions ?? null
    if (!list || !Array.isArray(list)) return null
    return await hydrateTransitionCandidates(list as TransitionCandidate[])
  } catch {
    return null
  }
}

/**
 * Score a single (from, to) pair and return the recommended transition
 * style + bar count. Used by the audio engine to pick crossfade length
 * dynamically instead of relying on the fixed `crossfadeBars` slider.
 *
 * Returns null when scoring is unavailable (missing features, MCP
 * error). Callers should fall back to their default crossfade.
 */
export async function getTransitionStyle(
  fromTrackId: number,
  toTrackId: number,
): Promise<PairScoreResult | null> {
  try {
    const result = await callTool('score_transitions', {
      mode: 'pair',
      from_track_id: fromTrackId,
      to_track_id: toTrackId,
    })
    const sc = result?.structured_content as
      | {
          from_track_id?: number
          to_track_id?: number
          overall_quality?: number | null
          hard_reject?: boolean
          reject_reason?: string | null
          recommended_style?: string | null
          recommended_bars?: number | null
        }
      | undefined
    if (!sc || sc.overall_quality == null) return null
    return {
      fromTrackId: sc.from_track_id ?? fromTrackId,
      toTrackId: sc.to_track_id ?? toTrackId,
      overall: sc.overall_quality ?? null,
      hardReject: sc.hard_reject ?? false,
      rejectReason: sc.reject_reason ?? null,
      recommendedStyle: (sc.recommended_style ?? null) as TransitionStyle | null,
      recommendedBars: sc.recommended_bars ?? null,
    }
  } catch {
    return null
  }
}

interface RawTrackRow {
  id: number
  title: string
  duration_ms: number | null
  track_audio_features_computed:
    | {
        bpm: number | null
        key_code: number | null
        mood: string | null
      }
    | Array<{
        bpm: number | null
        key_code: number | null
        mood: string | null
      }>
}

async function hydrateTransitionCandidates(
  candidates: TransitionCandidate[],
): Promise<TransitionCandidate[]> {
  if (candidates.length === 0) return candidates

  const ids = [...new Set(candidates.map((candidate) => candidate.to_track_id))]
  const supabase = await createClient()

  const [tracksResult, artistsResult, keysResult] = await Promise.all([
    supabase
      .from('tracks')
      .select(
        `
        id,
        title,
        duration_ms,
        track_audio_features_computed!left(
          bpm,
          key_code,
          mood
        )
      `,
      )
      .in('id', ids),
    supabase
      .from('track_artists')
      .select('track_id, artists!inner(name)')
      .in('track_id', ids)
      .eq('role', 'primary'),
    supabase.from('keys').select('key_code, camelot'),
  ])

  const artistMap = new Map<number, string[]>()
  for (const row of artistsResult.data ?? []) {
    const artist = Array.isArray(row.artists)
      ? row.artists[0]
      : (row.artists as { name?: string } | null)
    if (!artist?.name) continue
    const existing = artistMap.get(row.track_id) ?? []
    existing.push(artist.name)
    artistMap.set(row.track_id, existing)
  }

  const camelotMap = new Map<number, string>()
  for (const row of keysResult.data ?? []) {
    camelotMap.set(row.key_code, row.camelot)
  }

  const trackMap = new Map<number, TransitionCandidate>()
  for (const row of (tracksResult.data ?? []) as RawTrackRow[]) {
    const features = Array.isArray(row.track_audio_features_computed)
      ? row.track_audio_features_computed[0]
      : row.track_audio_features_computed
    const keyCode = features?.key_code ?? null
    trackMap.set(row.id, {
      to_track_id: row.id,
      overall_quality: 0,
      bpm_distance: null,
      energy_step: null,
      groove_similarity: null,
      key_distance_weighted: null,
      title: row.title,
      artists: (artistMap.get(row.id) ?? []).join(', '),
      duration_ms: row.duration_ms,
      bpm: features?.bpm ?? null,
      camelot: keyCode !== null ? (camelotMap.get(keyCode) ?? null) : null,
      mood: features?.mood ?? null,
    })
  }

  return candidates.map((candidate) => {
    const meta = trackMap.get(candidate.to_track_id)
    if (!meta) return candidate
    return {
      ...candidate,
      title: meta.title,
      artists: meta.artists,
      duration_ms: meta.duration_ms,
      bpm: candidate.bpm ?? meta.bpm ?? null,
      camelot: candidate.camelot ?? meta.camelot ?? null,
      mood: candidate.mood ?? meta.mood ?? null,
    }
  })
}
