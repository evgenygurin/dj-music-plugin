'use server'

import { createClient } from '@/lib/supabase/server'
import type { TrackRow } from '@/lib/queries/tracks'

export interface DefaultPickResult {
  first: TrackRow | null
  queue: TrackRow[]
}

// Row shape returned by the Supabase join below. Only the fields we actually
// map into TrackRow are listed — keep this private to this module.
interface RawFeatureRow {
  id: number
  title: string
  duration_ms: number | null
  status: number
  track_audio_features_computed:
    | {
        bpm: number | null
        key_code: number | null
        mood: string | null
        integrated_lufs: number | null
        energy_mean: number | null
        analysis_level: number | null
        mood_confidence: number | null
      }
    | Array<{
        bpm: number | null
        key_code: number | null
        mood: string | null
        integrated_lufs: number | null
        energy_mean: number | null
        analysis_level: number | null
        mood_confidence: number | null
      }>
}

function mapTrackRows(raw: RawFeatureRow[]): TrackRow[] {
  return raw.map((t) => {
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
    } satisfies TrackRow
  })
}

/**
 * Pick a broadcast-quality first track for the Layer 0 hero.
 *
 * Strategy:
 *   1. Prefer fully-analyzed, mood-classified tracks sorted by
 *      mood confidence (top 50 random pick)
 *   2. Fallback to any track with BPM
 *   3. Returns the pick + the pool of 50 as initial Compatibility queue
 */
export async function pickDefaultFirstTrack(): Promise<DefaultPickResult> {
  const supabase = await createClient()

  const { data: qualityRows } = await supabase
    .from('tracks')
    .select(
      `
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
    `,
    )
    .eq('status', 0)
    .gte('track_audio_features_computed.analysis_level', 4)
    .not('track_audio_features_computed.mood', 'is', null)
    .order('track_audio_features_computed.mood_confidence', { ascending: false })
    .limit(50)

  if (qualityRows && qualityRows.length > 0) {
    const rows = mapTrackRows(qualityRows as RawFeatureRow[])
    const pick = rows[Math.floor(Math.random() * rows.length)]
    return { first: pick, queue: rows }
  }

  const { data: anyRows } = await supabase
    .from('tracks')
    .select(
      `
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
    `,
    )
    .eq('status', 0)
    .not('track_audio_features_computed.bpm', 'is', null)
    .limit(50)

  if (!anyRows || anyRows.length === 0) {
    return { first: null, queue: [] }
  }
  const rows = mapTrackRows(anyRows as RawFeatureRow[])
  return { first: rows[0], queue: rows }
}
