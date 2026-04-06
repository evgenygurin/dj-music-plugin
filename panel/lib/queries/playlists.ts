import { createClient } from '@/lib/supabase/server'

export interface PlaylistListItem {
  id: number
  name: string
  parent_id: number | null
  source_of_truth: string | null
  source_app: string | null
  trackCount: number
}

export async function getPlaylistList(): Promise<PlaylistListItem[]> {
  const supabase = await createClient()

  const { data: playlists } = await supabase
    .from('dj_playlists')
    .select('id, name, parent_id, source_of_truth, source_app')
    .order('name')

  if (!playlists || playlists.length === 0) return []

  const playlistIds = playlists.map((p) => p.id)

  // Fetch all playlist items to count tracks per playlist
  const { data: items } = await supabase
    .from('dj_playlist_items')
    .select('playlist_id')
    .in('playlist_id', playlistIds)

  const countMap = new Map<number, number>()
  if (items) {
    for (const item of items) {
      countMap.set(item.playlist_id, (countMap.get(item.playlist_id) ?? 0) + 1)
    }
  }

  return playlists.map((p) => ({
    id: p.id,
    name: p.name,
    parent_id: p.parent_id ?? null,
    source_of_truth: p.source_of_truth ?? null,
    source_app: p.source_app ?? null,
    trackCount: countMap.get(p.id) ?? 0,
  }))
}

export interface PlaylistTrack {
  sort_index: number
  added_at: string | null
  track: {
    id: number
    title: string
    artists: string
    bpm: number | null
    key_code: number | null
    camelot: string | null
    mood: string | null
    integrated_lufs: number | null
  }
}

export interface MoodCount {
  mood: string
  count: number
}

export interface PlaylistDetail {
  id: number
  name: string
  parent_id: number | null
  source_of_truth: string | null
  platform_ids: Record<string, string> | null
  tracks: PlaylistTrack[]
  moodCounts: MoodCount[]
}

export async function getPlaylistDetail(id: number): Promise<PlaylistDetail | null> {
  const supabase = await createClient()

  // Fetch playlist info and items in parallel
  const [playlistResult, itemsResult] = await Promise.all([
    supabase
      .from('dj_playlists')
      .select('id, name, parent_id, source_of_truth, platform_ids')
      .eq('id', id)
      .single(),
    supabase
      .from('dj_playlist_items')
      .select('playlist_id, track_id, sort_index, added_at')
      .eq('playlist_id', id)
      .order('sort_index'),
  ])

  if (!playlistResult.data) return null

  const playlist = playlistResult.data
  const items = itemsResult.data ?? []

  if (items.length === 0) {
    return {
      id: playlist.id,
      name: playlist.name,
      parent_id: playlist.parent_id ?? null,
      source_of_truth: playlist.source_of_truth ?? null,
      platform_ids: (playlist.platform_ids as Record<string, string>) ?? null,
      tracks: [],
      moodCounts: [],
    }
  }

  const trackIds = [...new Set(items.map((i) => i.track_id).filter(Boolean))]

  // Fetch tracks, features, artists, keys in parallel
  const [tracksResult, featuresResult, keysResult] = await Promise.all([
    supabase.from('tracks').select('id, title').in('id', trackIds),
    supabase
      .from('track_audio_features_computed')
      .select('track_id, bpm, key_code, mood, integrated_lufs')
      .in('track_id', trackIds),
    supabase.from('keys').select('key_code, camelot'),
  ])

  // Fetch artist names
  const { data: artistsData } = await supabase
    .from('track_artists')
    .select('track_id, artists!inner(name)')
    .in('track_id', trackIds)
    .eq('role', 'primary')

  // Build lookup maps
  const trackMap = new Map<number, { id: number; title: string }>()
  for (const t of tracksResult.data ?? []) {
    trackMap.set(t.id, t)
  }

  const featuresMap = new Map<
    number,
    { bpm: number | null; key_code: number | null; mood: string | null; integrated_lufs: number | null }
  >()
  for (const f of featuresResult.data ?? []) {
    featuresMap.set(f.track_id, {
      bpm: f.bpm ?? null,
      key_code: f.key_code ?? null,
      mood: f.mood ?? null,
      integrated_lufs: f.integrated_lufs ?? null,
    })
  }

  const camelotMap = new Map<number, string>()
  for (const k of keysResult.data ?? []) {
    camelotMap.set(k.key_code, k.camelot)
  }

  const artistMap = new Map<number, string[]>()
  for (const row of artistsData ?? []) {
    const name = Array.isArray(row.artists)
      ? row.artists[0]?.name
      : (row.artists as { name: string })?.name
    if (name) {
      const existing = artistMap.get(row.track_id) ?? []
      existing.push(name)
      artistMap.set(row.track_id, existing)
    }
  }

  // Build tracks list
  const tracks: PlaylistTrack[] = items
    .filter((item) => item.track_id !== null)
    .map((item) => {
      const features = featuresMap.get(item.track_id)
      const keyCode = features?.key_code ?? null

      return {
        sort_index: item.sort_index,
        added_at: item.added_at ?? null,
        track: {
          id: item.track_id,
          title: trackMap.get(item.track_id)?.title ?? '',
          artists: (artistMap.get(item.track_id) ?? []).join(', '),
          bpm: features?.bpm ?? null,
          key_code: keyCode,
          camelot: keyCode !== null ? (camelotMap.get(keyCode) ?? null) : null,
          mood: features?.mood ?? null,
          integrated_lufs: features?.integrated_lufs ?? null,
        },
      }
    })

  // Compute mood counts
  const moodCountMap = new Map<string, number>()
  for (const item of tracks) {
    const mood = item.track.mood
    if (mood) {
      moodCountMap.set(mood, (moodCountMap.get(mood) ?? 0) + 1)
    }
  }

  const moodCounts: MoodCount[] = Array.from(moodCountMap.entries())
    .map(([mood, count]) => ({ mood, count }))
    .sort((a, b) => b.count - a.count)

  return {
    id: playlist.id,
    name: playlist.name,
    parent_id: playlist.parent_id ?? null,
    source_of_truth: playlist.source_of_truth ?? null,
    platform_ids: (playlist.platform_ids as Record<string, string>) ?? null,
    tracks,
    moodCounts,
  }
}
