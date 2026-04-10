'use server'

import { createClient } from '@/lib/supabase/server'
import { getTrackList, type TrackListParams, type TrackRow } from '@/lib/queries/tracks'

export interface LoadMoreResult {
  tracks: TrackRow[]
  total: number
  hasMore: boolean
  nextPage: number
}

// Camelot notation lookup (key_code 0-23 → "1A"-"12B")
const CAMELOT: Record<number, string> = {
  0:  '5A',  1: '12A', 2:  '7A',  3:  '2A',  4:  '9A',  5:  '4A',
  6: '11A',  7:  '6A', 8:  '1A',  9:  '8A', 10:  '3A', 11: '10A',
  12: '5B', 13: '12B', 14:  '7B', 15:  '2B', 16:  '9B', 17:  '4B',
  18:'11B', 19:  '6B', 20:  '1B', 21:  '8B', 22:  '3B', 23: '10B',
}

/** Load 500 tracks with BPM near the given value for auto-DJ queue. */
export async function loadDjQueue(bpm: number): Promise<Array<{
  id: number; title: string; artists: string | null
  bpm: number | null; camelot: string | null; mood: string | null
  duration_ms: number | null
}>> {
  const supabase = await createClient()
  // Two fast queries instead of one heavy join
  const { data: features } = await supabase
    .from('track_audio_features_computed')
    .select('track_id, bpm, key_code, mood')
    .gte('bpm', bpm - 5)
    .lte('bpm', bpm + 5)
    .not('bpm', 'is', null)
    .limit(500)

  if (!features || features.length === 0) return []

  const trackIds = features.map((f: { track_id: number }) => f.track_id)
  const { data: tracks } = await supabase
    .from('tracks')
    .select('id, title, duration_ms')
    .in('id', trackIds)

  const trackMap = new Map<number, { title: string; duration_ms: number | null }>()
  for (const t of tracks ?? []) {
    trackMap.set(t.id, { title: t.title, duration_ms: t.duration_ms })
  }

  return features.map((f: { track_id: number; bpm: number | null; key_code: number | null; mood: string | null }) => {
    const track = trackMap.get(f.track_id)
    return {
      id: f.track_id,
      title: track?.title ?? '?',
      artists: null,
      bpm: f.bpm,
      camelot: f.key_code != null ? (CAMELOT[f.key_code] ?? null) : null,
      mood: f.mood,
      duration_ms: track?.duration_ms ?? null,
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
