import { createClient } from '@/lib/supabase/server'

export interface TrackRow {
  id: number
  title: string
  duration_ms: number | null
  status: number
  artists: string
  bpm: number | null
  key_code: number | null
  camelot: string | null
  mood: string | null
  integrated_lufs: number | null
  energy_mean: number | null
  analysis_level: number | null
}

export interface TrackListParams {
  page?: number
  pageSize?: number
  sortBy?: 'title' | 'bpm' | 'integrated_lufs' | 'energy_mean' | 'duration_ms'
  sortDir?: 'asc' | 'desc'
  bpmMin?: number
  bpmMax?: number
  mood?: string
  keyCode?: number
  search?: string
}

export interface TrackListResult {
  tracks: TrackRow[]
  total: number
}

export async function getTrackList(params: TrackListParams = {}): Promise<TrackListResult> {
  const supabase = await createClient()

  const {
    page = 1,
    pageSize = 50,
    sortBy = 'title',
    sortDir = 'asc',
    bpmMin,
    bpmMax,
    mood,
    keyCode,
    search,
  } = params

  const from = (page - 1) * pageSize
  const to = from + pageSize - 1

  // Build tracks query with left-joined features
  let tracksQuery = supabase
    .from('tracks')
    .select(
      `
      id,
      title,
      duration_ms,
      status,
      track_audio_features_computed!left(
        bpm,
        key_code,
        mood,
        integrated_lufs,
        energy_mean,
        analysis_level
      )
    `,
      { count: 'exact' },
    )
    .eq('status', 0)

  if (search) {
    tracksQuery = tracksQuery.ilike('title', `%${search}%`)
  }

  if (bpmMin !== undefined) {
    tracksQuery = tracksQuery.gte('track_audio_features_computed.bpm', bpmMin)
  }
  if (bpmMax !== undefined) {
    tracksQuery = tracksQuery.lte('track_audio_features_computed.bpm', bpmMax)
  }
  if (mood) {
    tracksQuery = tracksQuery.eq('track_audio_features_computed.mood', mood)
  }
  if (keyCode !== undefined) {
    tracksQuery = tracksQuery.eq('track_audio_features_computed.key_code', keyCode)
  }

  // Sort: features columns require special handling — sort on tracks columns directly
  const trackSortColumns = ['title', 'duration_ms']
  if (trackSortColumns.includes(sortBy)) {
    tracksQuery = tracksQuery.order(sortBy, { ascending: sortDir === 'asc' })
  } else {
    tracksQuery = tracksQuery.order('title', { ascending: true })
  }

  tracksQuery = tracksQuery.range(from, to)

  const { data: tracksData, count: total, error } = await tracksQuery

  if (error) throw error
  if (!tracksData) return { tracks: [], total: 0 }

  const trackIds = tracksData.map((t) => t.id)

  // Fetch artist names for these tracks
  const artistsPromise =
    trackIds.length > 0
      ? supabase
          .from('track_artists')
          .select('track_id, artists!inner(name)')
          .in('track_id', trackIds)
          .eq('role', 'primary')
      : Promise.resolve({ data: [] as Array<{ track_id: number; artists: { name: string } | Array<{ name: string }> }> })

  // Fetch key camelot notations
  const keysPromise = supabase.from('keys').select('key_code, camelot')

  const [artistsResult, keysResult] = await Promise.all([artistsPromise, keysPromise])

  // Build lookup maps
  const artistMap = new Map<number, string[]>()
  if (artistsResult.data) {
    for (const row of artistsResult.data) {
      const name = Array.isArray(row.artists) ? row.artists[0]?.name : (row.artists as { name: string })?.name
      if (name) {
        const existing = artistMap.get(row.track_id) ?? []
        existing.push(name)
        artistMap.set(row.track_id, existing)
      }
    }
  }

  const camelotMap = new Map<number, string>()
  if (keysResult.data) {
    for (const k of keysResult.data) {
      camelotMap.set(k.key_code, k.camelot)
    }
  }

  // Merge results
  const tracks: TrackRow[] = tracksData.map((t) => {
    const features = Array.isArray(t.track_audio_features_computed)
      ? t.track_audio_features_computed[0]
      : t.track_audio_features_computed

    const keyCode = features?.key_code ?? null

    return {
      id: t.id,
      title: t.title,
      duration_ms: t.duration_ms,
      status: t.status,
      artists: (artistMap.get(t.id) ?? []).join(', '),
      bpm: features?.bpm ?? null,
      key_code: keyCode,
      camelot: keyCode !== null ? (camelotMap.get(keyCode) ?? null) : null,
      mood: features?.mood ?? null,
      integrated_lufs: features?.integrated_lufs ?? null,
      energy_mean: features?.energy_mean ?? null,
      analysis_level: features?.analysis_level ?? null,
    }
  })

  // Sort by features columns in JS if needed
  if (!trackSortColumns.includes(sortBy)) {
    tracks.sort((a, b) => {
      const aVal = a[sortBy as keyof TrackRow] as number | null
      const bVal = b[sortBy as keyof TrackRow] as number | null
      if (aVal === null && bVal === null) return 0
      if (aVal === null) return 1
      if (bVal === null) return -1
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }

  return { tracks, total: total ?? 0 }
}

export interface TrackArtist {
  id: number
  name: string
  role: string
}

export interface TrackFeatures {
  bpm: number | null
  key_code: number | null
  camelot: string | null
  mood: string | null
  mood_confidence: number | null
  integrated_lufs: number | null
  short_term_lufs_mean: number | null
  energy_mean: number | null
  energy_max: number | null
  spectral_centroid_hz: number | null
  spectral_flatness: number | null
  spectral_flux_mean: number | null
  onset_rate: number | null
  kick_prominence: number | null
  pulse_clarity: number | null
  hp_ratio: number | null
  mfcc_vector: number[] | null
  chroma_vector: number[] | null
  analysis_level: number | null
}

export interface TrackSection {
  id: number
  section_type: number
  start_ms: number
  end_ms: number
  energy: number | null
  confidence: number | null
}

export interface CuePoint {
  id: number
  position_ms: number
  kind: number
  hotcue_index: number | null
  label: string | null
  color: string | null
}

export interface SavedLoop {
  id: number
  in_position_ms: number
  out_position_ms: number
  label: string | null
  color: string | null
}

export interface LibraryItem {
  id: number
  file_path: string
  file_size: number | null
  bitrate: number | null
  sample_rate: number | null
  channels: number | null
}

export interface YmMetadata {
  yandex_track_id: string | null
  album_id: number | null
  album_title: string | null
  cover_uri: string | null
  explicit: boolean | null
}

export interface TrackDetail {
  id: number
  title: string
  sort_title: string | null
  duration_ms: number | null
  status: number
  created_at: string | null
  updated_at: string | null
  artists: TrackArtist[]
  features: TrackFeatures | null
  sections: TrackSection[]
  cuePoints: CuePoint[]
  loops: SavedLoop[]
  libraryItem: LibraryItem | null
  ymMetadata: YmMetadata | null
}

export async function getTrackDetail(id: number): Promise<TrackDetail | null> {
  const supabase = await createClient()

  // Fetch core track data
  const { data: track } = await supabase
    .from('tracks')
    .select('id, title, sort_title, duration_ms, status, created_at, updated_at')
    .eq('id', id)
    .single()

  if (!track) return null

  // Parallel fetch all related data
  const [
    artistsResult,
    featuresResult,
    sectionsResult,
    libraryItemResult,
    ymResult,
    keysResult,
  ] = await Promise.all([
    supabase
      .from('track_artists')
      .select('role, artists!inner(id, name)')
      .eq('track_id', id),
    supabase
      .from('track_audio_features_computed')
      .select('*')
      .eq('track_id', id)
      .single(),
    supabase
      .from('track_sections')
      .select('id, section_type, start_ms, end_ms, energy, confidence')
      .eq('track_id', id)
      .order('start_ms'),
    supabase
      .from('dj_library_items')
      .select('id, file_path, file_size, bitrate, sample_rate, channels')
      .eq('track_id', id)
      .limit(1)
      .maybeSingle(),
    supabase
      .from('yandex_metadata')
      .select('yandex_track_id, album_id, album_title, cover_uri, explicit')
      .eq('track_id', id)
      .maybeSingle(),
    supabase.from('keys').select('key_code, camelot'),
  ])

  // Build camelot map
  const camelotMap = new Map<number, string>()
  if (keysResult.data) {
    for (const k of keysResult.data) {
      camelotMap.set(k.key_code, k.camelot)
    }
  }

  // Parse artists
  const artists: TrackArtist[] = []
  if (artistsResult.data) {
    for (const row of artistsResult.data) {
      const artist = Array.isArray(row.artists) ? row.artists[0] : row.artists as { id: number; name: string }
      if (artist) {
        artists.push({ id: artist.id, name: artist.name, role: row.role })
      }
    }
  }

  // Parse features
  let features: TrackFeatures | null = null
  if (featuresResult.data) {
    const f = featuresResult.data
    const keyCode: number | null = f.key_code ?? null
    features = {
      bpm: f.bpm ?? null,
      key_code: keyCode,
      camelot: keyCode !== null ? (camelotMap.get(keyCode) ?? null) : null,
      mood: f.mood ?? null,
      mood_confidence: f.mood_confidence ?? null,
      integrated_lufs: f.integrated_lufs ?? null,
      short_term_lufs_mean: f.short_term_lufs_mean ?? null,
      energy_mean: f.energy_mean ?? null,
      energy_max: f.energy_max ?? null,
      spectral_centroid_hz: f.spectral_centroid_hz ?? null,
      spectral_flatness: f.spectral_flatness ?? null,
      spectral_flux_mean: f.spectral_flux_mean ?? null,
      onset_rate: f.onset_rate ?? null,
      kick_prominence: f.kick_prominence ?? null,
      pulse_clarity: f.pulse_clarity ?? null,
      hp_ratio: f.hp_ratio ?? null,
      mfcc_vector: f.mfcc_vector ?? null,
      chroma_vector: f.chroma_vector ?? null,
      analysis_level: f.analysis_level ?? null,
    }
  }

  // Parse sections
  const sections: TrackSection[] = (sectionsResult.data ?? []).map((s) => ({
    id: s.id,
    section_type: s.section_type,
    start_ms: s.start_ms,
    end_ms: s.end_ms,
    energy: s.energy ?? null,
    confidence: s.confidence ?? null,
  }))

  // Fetch cue points and loops via library_item_id
  const libraryItem = libraryItemResult.data ?? null
  let cuePoints: CuePoint[] = []
  let loops: SavedLoop[] = []

  if (libraryItem) {
    const [cueResult, loopResult] = await Promise.all([
      supabase
        .from('dj_cue_points')
        .select('id, position_ms, kind, hotcue_index, label, color')
        .eq('library_item_id', libraryItem.id)
        .order('position_ms'),
      supabase
        .from('dj_saved_loops')
        .select('id, in_position_ms, out_position_ms, label, color')
        .eq('library_item_id', libraryItem.id)
        .order('in_position_ms'),
    ])

    cuePoints = (cueResult.data ?? []).map((c) => ({
      id: c.id,
      position_ms: c.position_ms,
      kind: c.kind,
      hotcue_index: c.hotcue_index ?? null,
      label: c.label ?? null,
      color: c.color ?? null,
    }))

    loops = (loopResult.data ?? []).map((l) => ({
      id: l.id,
      in_position_ms: l.in_position_ms,
      out_position_ms: l.out_position_ms,
      label: l.label ?? null,
      color: l.color ?? null,
    }))
  }

  const ymMetadata: YmMetadata | null = ymResult.data
    ? {
        yandex_track_id: ymResult.data.yandex_track_id ?? null,
        album_id: ymResult.data.album_id ?? null,
        album_title: ymResult.data.album_title ?? null,
        cover_uri: ymResult.data.cover_uri ?? null,
        explicit: ymResult.data.explicit ?? null,
      }
    : null

  return {
    id: track.id,
    title: track.title,
    sort_title: track.sort_title ?? null,
    duration_ms: track.duration_ms ?? null,
    status: track.status,
    created_at: track.created_at ?? null,
    updated_at: track.updated_at ?? null,
    artists,
    features,
    sections,
    cuePoints,
    loops,
    libraryItem: libraryItem
      ? {
          id: libraryItem.id,
          file_path: libraryItem.file_path,
          file_size: libraryItem.file_size ?? null,
          bitrate: libraryItem.bitrate ?? null,
          sample_rate: libraryItem.sample_rate ?? null,
          channels: libraryItem.channels ?? null,
        }
      : null,
    ymMetadata,
  }
}
