'use server'

import { createClient } from '@/lib/supabase/server'
import { getTrackList, type TrackListParams, type TrackRow } from '@/lib/queries/tracks'

export interface LoadMoreResult {
  tracks: TrackRow[]
  total: number
  hasMore: boolean
  nextPage: number
}

/** Load 500 tracks with BPM near the given value for auto-DJ queue. */
export async function loadDjQueue(bpm: number): Promise<Array<{
  id: number; title: string; artists: string | null
  bpm: number | null; camelot: string | null; mood: string | null
  duration_ms: number | null
}>> {
  const supabase = await createClient()
  const bpmMin = bpm - 5
  const bpmMax = bpm + 5
  const { data } = await supabase
    .from('track_audio_features_computed')
    .select(`
      track_id,
      bpm,
      mood,
      tracks!inner(id, title, duration_ms),
      keys:key_code(camelot)
    `)
    .gte('bpm', bpmMin)
    .lte('bpm', bpmMax)
    .not('bpm', 'is', null)
    .limit(500)

  if (!data) return []

  // Flatten join result
  return data.map((row: Record<string, unknown>) => {
    const track = row.tracks as Record<string, unknown> | null
    const key = row.keys as Record<string, unknown> | null
    return {
      id: (track?.id as number) ?? (row.track_id as number),
      title: (track?.title as string) ?? '?',
      artists: null,
      bpm: row.bpm as number | null,
      camelot: (key?.camelot as string) ?? null,
      mood: (row.mood as string) ?? null,
      duration_ms: (track?.duration_ms as number) ?? null,
    }
  })
}

export async function loadMoreTracks(params: TrackListParams): Promise<LoadMoreResult> {
  const result = await getTrackList(params)
  const page = params.page ?? 1
  const pageSize = params.pageSize ?? 50
  return {
    tracks: result.tracks,
    total: result.total,
    hasMore: page * pageSize < result.total,
    nextPage: page + 1,
  }
}
