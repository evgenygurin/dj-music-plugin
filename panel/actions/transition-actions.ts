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

const CANDIDATE_POOL_BPM_RADIUS = 8
const CANDIDATE_POOL_MAX = 200

/**
 * Score the best matching next tracks for a given source track.
 *
 * v1.0 mapping: legacy `score_transitions(mode="track_candidates",
 * track_id, top_n)` is decomposed into:
 *   1. Read source BPM via Supabase + pull `CANDIDATE_POOL_MAX` candidates
 *      with BPM within ±`CANDIDATE_POOL_BPM_RADIUS` (the v1 `transition_
 *      score_pool` caps at 500; this prunes early so we stay well under).
 *   2. `transition_score_pool(track_ids=[source, ...candidates])` — returns
 *      N*(N-1) directed pairs, including the (source → candidate) ones we
 *      need.
 *   3. Filter to pairs where `a == sourceId`, sort by overall desc, slice
 *      top-N.
 *
 * Returns null when the source has no audio features (cannot prune the
 * pool by BPM) so the caller can fall back to the lightweight client-side
 * heuristic.
 */
export async function scoreTransitionCandidates(
  fromTrackId: number,
  topN: number = 20,
): Promise<TransitionCandidate[] | null> {
  try {
    const supabase = await createClient()

    // 1. Source BPM (needed to prune the candidate pool).
    const { data: srcFeat } = await supabase
      .from('track_audio_features_computed')
      .select('bpm')
      .eq('track_id', fromTrackId)
      .single()
    const srcBpm = srcFeat?.bpm
    if (typeof srcBpm !== 'number') return null

    // 2. Pull a BPM-pruned candidate pool.
    const { data: poolRows } = await supabase
      .from('track_audio_features_computed')
      .select('track_id, bpm')
      .gte('bpm', srcBpm - CANDIDATE_POOL_BPM_RADIUS)
      .lte('bpm', srcBpm + CANDIDATE_POOL_BPM_RADIUS)
      .neq('track_id', fromTrackId)
      .not('bpm', 'is', null)
      .limit(CANDIDATE_POOL_MAX)
    if (!poolRows || poolRows.length === 0) return []

    const candidateIds = poolRows.map(
      (r: { track_id: number }) => r.track_id,
    )
    const trackIds = [fromTrackId, ...candidateIds]

    // 3. Score N*(N-1) pairs, then keep only (source → candidate) edges.
    const result = await callTool('transition_score_pool', { track_ids: trackIds })
    if (result.is_error || !result.structured_content) return null
    const sc = result.structured_content as {
      pairs?: Array<{
        a: number
        b: number
        overall: number
        bpm: number
        harmonic: number
        energy: number
        spectral: number
        groove: number
        timbral: number
      }>
    }
    const pairs = sc.pairs ?? []
    const fromSource = pairs
      .filter((p) => p.a === fromTrackId)
      .map(
        (p): TransitionCandidate => ({
          to_track_id: p.b,
          overall_quality: p.overall,
          bpm_distance: null,
          energy_step: null,
          groove_similarity: p.groove,
          key_distance_weighted: null,
        }),
      )
      .sort((x, y) => y.overall_quality - x.overall_quality)
      .slice(0, topN)

    return await hydrateTransitionCandidates(fromSource)
  } catch {
    return null
  }
}

/**
 * Score a single (from, to) pair and return the recommended transition
 * style + bar count.
 *
 * v1.0 mapping: legacy `score_transitions(mode="pair", from_track_id,
 * to_track_id)` → `read_resource(uri="local://transition/{from}/{to}/score")`.
 *
 * Note: the v1 transition resource does NOT include `recommended_style` /
 * `recommended_bars` — those were a legacy add-on. The audio engine
 * receives `recommendedStyle: null` here and falls back to its default
 * crossfade style (manual chip / `fade`).
 *
 * TODO(v1.0-actions-rewrite): expose `recommend_style` from the backend
 * (it lives in `app.domain.transition.style:recommend_style`) — either
 * via a tool extension or by extending the local://transition resource
 * payload.
 */
export async function getTransitionStyle(
  fromTrackId: number,
  toTrackId: number,
): Promise<PairScoreResult | null> {
  try {
    const result = await callTool('read_resource', {
      uri: `local://transition/${fromTrackId}/${toTrackId}/score`,
    })
    if (result.is_error) return null
    const sc = extractTransitionScore(result.structured_content, result.content)
    if (!sc) return null
    if (sc.overall == null) return null
    return {
      fromTrackId: sc.from_track_id ?? fromTrackId,
      toTrackId: sc.to_track_id ?? toTrackId,
      overall: sc.overall ?? null,
      hardReject: sc.hard_reject ?? false,
      rejectReason: sc.reject_reason ?? null,
      // v1 transition resource does not carry style — engine uses default.
      recommendedStyle: null,
      recommendedBars: null,
    }
  } catch {
    return null
  }
}

interface RawTransitionScorePayload {
  from_track_id?: number
  to_track_id?: number
  overall?: number | null
  hard_reject?: boolean
  reject_reason?: string | null
}

function extractTransitionScore(
  structured: Record<string, unknown> | null,
  content: Array<{ type: string; text?: string }>,
): RawTransitionScorePayload | null {
  if (structured) {
    const direct = structured as RawTransitionScorePayload
    if ('overall' in direct || 'from_track_id' in direct) return direct
    const wrapped = structured as Record<string, unknown>
    const result = wrapped.result as RawTransitionScorePayload | undefined
    if (result) return result
    const contents = wrapped.contents as Array<{ text?: string }> | undefined
    if (Array.isArray(contents) && contents[0]?.text) {
      try {
        return JSON.parse(contents[0].text) as RawTransitionScorePayload
      } catch {
        // fall through
      }
    }
  }
  for (const item of content) {
    if (item.type === 'text' && item.text) {
      try {
        return JSON.parse(item.text) as RawTransitionScorePayload
      } catch {
        // try next
      }
    }
  }
  return null
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
