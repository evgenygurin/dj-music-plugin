import { createClient } from '@/lib/supabase/server'

export interface SetVersionSummary {
  id: number
  label: string | null
  quality_score: number | null
}

export interface SetListItem {
  id: number
  name: string
  template_name: string | null
  target_duration_ms: number | null
  target_bpm_min: number | null
  target_bpm_max: number | null
  created_at: string | null
  latestVersion: SetVersionSummary | null
  trackCount: number
  versionCount: number
}

export async function getSetList(): Promise<SetListItem[]> {
  const supabase = await createClient()

  const { data: sets } = await supabase
    .from('dj_sets')
    .select('id, name, template_name, target_duration_ms, target_bpm_min, target_bpm_max, created_at')
    .order('created_at', { ascending: false })

  if (!sets || sets.length === 0) return []

  const setIds = sets.map((s) => s.id)

  // Fetch all versions for these sets
  const { data: versions } = await supabase
    .from('dj_set_versions')
    .select('id, set_id, label, quality_score, created_at')
    .in('set_id', setIds)
    .order('created_at', { ascending: false })

  // Group versions by set_id
  const versionsBySet = new Map<number, typeof versions>()
  if (versions) {
    for (const v of versions) {
      const existing = versionsBySet.get(v.set_id) ?? []
      existing.push(v)
      versionsBySet.set(v.set_id, existing)
    }
  }

  // Get track counts per set via latest version
  const latestVersionIds: number[] = []
  const latestVersionBySet = new Map<number, NonNullable<typeof versions>[number]>()
  if (versions) {
    for (const [setId, setVersions] of versionsBySet.entries()) {
      if (setVersions && setVersions.length > 0) {
        const latest = setVersions[0]!
        latestVersionBySet.set(setId, latest)
        latestVersionIds.push(latest.id)
      }
    }
  }

  // Fetch item counts per version
  const trackCountBySet = new Map<number, number>()
  if (latestVersionIds.length > 0) {
    const { data: items } = await supabase
      .from('dj_set_items')
      .select('version_id')
      .in('version_id', latestVersionIds)

    if (items) {
      const countByVersion = new Map<number, number>()
      for (const item of items) {
        countByVersion.set(item.version_id, (countByVersion.get(item.version_id) ?? 0) + 1)
      }

      for (const [setId, latestVersion] of latestVersionBySet.entries()) {
        trackCountBySet.set(setId, countByVersion.get(latestVersion.id) ?? 0)
      }
    }
  }

  return sets.map((s) => {
    const setVersions = versionsBySet.get(s.id) ?? []
    const latestVersion = latestVersionBySet.get(s.id) ?? null

    return {
      id: s.id,
      name: s.name,
      template_name: s.template_name ?? null,
      target_duration_ms: s.target_duration_ms ?? null,
      target_bpm_min: s.target_bpm_min ?? null,
      target_bpm_max: s.target_bpm_max ?? null,
      created_at: s.created_at ?? null,
      latestVersion: latestVersion
        ? {
            id: latestVersion.id,
            label: latestVersion.label ?? null,
            quality_score: latestVersion.quality_score ?? null,
          }
        : null,
      trackCount: trackCountBySet.get(s.id) ?? 0,
      versionCount: setVersions.length,
    }
  })
}

export interface SetVersion {
  id: number
  label: string | null
  quality_score: number | null
  created_at: string | null
}

export interface SetConstraint {
  id: number
  constraint_type: string
  value: unknown
}

export interface SetDetail {
  id: number
  name: string
  description: string | null
  template_name: string | null
  target_duration_ms: number | null
  target_bpm_min: number | null
  target_bpm_max: number | null
  target_energy_arc: unknown | null
  source_playlist_id: number | null
  versions: SetVersion[]
  constraints: SetConstraint[]
}

export async function getSetDetail(id: number): Promise<SetDetail | null> {
  const supabase = await createClient()

  const [setResult, versionsResult, constraintsResult] = await Promise.all([
    supabase
      .from('dj_sets')
      .select(
        'id, name, description, template_name, target_duration_ms, target_bpm_min, target_bpm_max, target_energy_arc, source_playlist_id',
      )
      .eq('id', id)
      .single(),
    supabase
      .from('dj_set_versions')
      .select('id, label, quality_score, created_at')
      .eq('set_id', id)
      .order('created_at', { ascending: false }),
    supabase
      .from('dj_set_constraints')
      .select('id, constraint_type, value')
      .eq('set_id', id),
  ])

  if (!setResult.data) return null

  const s = setResult.data

  return {
    id: s.id,
    name: s.name,
    description: s.description ?? null,
    template_name: s.template_name ?? null,
    target_duration_ms: s.target_duration_ms ?? null,
    target_bpm_min: s.target_bpm_min ?? null,
    target_bpm_max: s.target_bpm_max ?? null,
    target_energy_arc: s.target_energy_arc ?? null,
    source_playlist_id: s.source_playlist_id ?? null,
    versions: (versionsResult.data ?? []).map((v) => ({
      id: v.id,
      label: v.label ?? null,
      quality_score: v.quality_score ?? null,
      created_at: v.created_at ?? null,
    })),
    constraints: (constraintsResult.data ?? []).map((c) => ({
      id: c.id,
      constraint_type: c.constraint_type,
      value: c.value,
    })),
  }
}

export interface SetVersionTrackInfo {
  id: number
  title: string
  artists: string
  bpm: number | null
  key_code: number | null
  camelot: string | null
  mood: string | null
  integrated_lufs: number | null
  energy_mean: number | null
}

export interface SetVersionTransition {
  overall_quality: number | null
  bpm_score: number | null
  harmonic_score: number | null
  energy_score: number | null
  spectral_score: number | null
  groove_score: number | null
}

export interface SetVersionTrack {
  sort_index: number
  pinned: boolean
  notes: string | null
  mix_in_point_ms: number | null
  mix_out_point_ms: number | null
  track: SetVersionTrackInfo
  transition: SetVersionTransition | null
}

export async function getSetVersionTracks(versionId: number): Promise<SetVersionTrack[]> {
  const supabase = await createClient()

  // Fetch set items
  const { data: items } = await supabase
    .from('dj_set_items')
    .select('sort_index, pinned, notes, mix_in_point_ms, mix_out_point_ms, track_id, transition_id')
    .eq('version_id', versionId)
    .order('sort_index')

  if (!items || items.length === 0) return []

  const trackIds = [...new Set(items.map((i) => i.track_id).filter(Boolean))]
  const transitionIds = [...new Set(items.map((i) => i.transition_id).filter(Boolean))]

  // Parallel fetch tracks, features, artists, transitions, keys
  const [tracksResult, featuresResult, transitionsResult, keysResult] = await Promise.all([
    trackIds.length > 0
      ? supabase.from('tracks').select('id, title').in('id', trackIds)
      : Promise.resolve({ data: [] as Array<{ id: number; title: string }> }),
    trackIds.length > 0
      ? supabase
          .from('track_audio_features_computed')
          .select('track_id, bpm, key_code, mood, integrated_lufs, energy_mean')
          .in('track_id', trackIds)
      : Promise.resolve({ data: [] as Array<{ track_id: number; bpm: number | null; key_code: number | null; mood: string | null; integrated_lufs: number | null; energy_mean: number | null }> }),
    transitionIds.length > 0
      ? supabase
          .from('transitions')
          .select('id, overall_quality, bpm_score, harmonic_score, energy_score, spectral_score, groove_score')
          .in('id', transitionIds)
      : Promise.resolve({ data: [] as Array<{ id: number; overall_quality: number | null; bpm_score: number | null; harmonic_score: number | null; energy_score: number | null; spectral_score: number | null; groove_score: number | null }> }),
    supabase.from('keys').select('key_code, camelot'),
  ])

  // Fetch artist names
  const { data: artistsData } = trackIds.length > 0
    ? await supabase
        .from('track_artists')
        .select('track_id, artists!inner(name)')
        .in('track_id', trackIds)
        .eq('role', 'primary')
    : { data: [] as Array<{ track_id: number; artists: { name: string } | Array<{ name: string }> }> }

  // Build lookup maps
  const trackMap = new Map<number, { id: number; title: string }>()
  for (const t of tracksResult.data ?? []) {
    trackMap.set(t.id, t)
  }

  const featuresMap = new Map<number, NonNullable<typeof featuresResult.data>[number]>()
  for (const f of featuresResult.data ?? []) {
    featuresMap.set(f.track_id, f)
  }

  const transitionMap = new Map<number, NonNullable<typeof transitionsResult.data>[number]>()
  for (const t of transitionsResult.data ?? []) {
    transitionMap.set(t.id, t)
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

  return items
    .filter((item) => item.track_id !== null)
    .map((item) => {
      const track = trackMap.get(item.track_id)
      const features = featuresMap.get(item.track_id)
      const transition = item.transition_id ? transitionMap.get(item.transition_id) : null
      const keyCode = features?.key_code ?? null

      return {
        sort_index: item.sort_index,
        pinned: item.pinned ?? false,
        notes: item.notes ?? null,
        mix_in_point_ms: item.mix_in_point_ms ?? null,
        mix_out_point_ms: item.mix_out_point_ms ?? null,
        track: {
          id: item.track_id,
          title: track?.title ?? '',
          artists: (artistMap.get(item.track_id) ?? []).join(', '),
          bpm: features?.bpm ?? null,
          key_code: keyCode,
          camelot: keyCode !== null ? (camelotMap.get(keyCode) ?? null) : null,
          mood: features?.mood ?? null,
          integrated_lufs: features?.integrated_lufs ?? null,
          energy_mean: features?.energy_mean ?? null,
        },
        transition: transition
          ? {
              overall_quality: transition.overall_quality ?? null,
              bpm_score: transition.bpm_score ?? null,
              harmonic_score: transition.harmonic_score ?? null,
              energy_score: transition.energy_score ?? null,
              spectral_score: transition.spectral_score ?? null,
              groove_score: transition.groove_score ?? null,
            }
          : null,
      }
    })
}
