import { createClient } from '@/lib/supabase/server'

export interface LibraryStats {
  totalTracks: number
  analyzedTracks: number
  totalSets: number
  libraryItems: number
  avgSetQuality: number | null
}

export interface BpmBin {
  bin: number
  count: number
}

export interface MoodCount {
  mood: string
  count: number
}

export interface KeyCount {
  camelot: string
  count: number
}

export interface LufsBin {
  lufs: number
  count: number
}

export interface AnalysisLevelCount {
  level: number
  count: number
}

export async function getLibraryStats(): Promise<LibraryStats> {
  const supabase = await createClient()

  const [tracksResult, analyzedResult, setsResult, libraryResult, qualityResult] =
    await Promise.all([
      supabase.from('tracks').select('*', { count: 'exact', head: true }),
      supabase
        .from('track_audio_features_computed')
        .select('*', { count: 'exact', head: true })
        .not('bpm', 'is', null),
      supabase.from('dj_sets').select('*', { count: 'exact', head: true }),
      supabase.from('dj_library_items').select('*', { count: 'exact', head: true }),
      supabase.from('dj_set_versions').select('quality_score'),
    ])

  let avgSetQuality: number | null = null
  if (qualityResult.data && qualityResult.data.length > 0) {
    const scores = qualityResult.data
      .map((v) => v.quality_score)
      .filter((s): s is number => s !== null && s !== undefined)
    if (scores.length > 0) {
      avgSetQuality = scores.reduce((a, b) => a + b, 0) / scores.length
    }
  }

  return {
    totalTracks: tracksResult.count ?? 0,
    analyzedTracks: analyzedResult.count ?? 0,
    totalSets: setsResult.count ?? 0,
    libraryItems: libraryResult.count ?? 0,
    avgSetQuality,
  }
}

export async function getBpmDistribution(): Promise<BpmBin[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('bpm')
    .not('bpm', 'is', null)
    .gte('bpm', 80)
    .lte('bpm', 200)

  if (!data || data.length === 0) return []

  const binSize = 5
  const binMap = new Map<number, number>()

  for (const row of data) {
    if (row.bpm === null || row.bpm === undefined) continue
    const bin = Math.floor(row.bpm / binSize) * binSize
    binMap.set(bin, (binMap.get(bin) ?? 0) + 1)
  }

  return Array.from(binMap.entries())
    .map(([bin, count]) => ({ bin, count }))
    .sort((a, b) => a.bin - b.bin)
}

export async function getMoodDistribution(): Promise<MoodCount[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('mood')
    .not('mood', 'is', null)

  if (!data || data.length === 0) return []

  const moodMap = new Map<string, number>()

  for (const row of data) {
    if (!row.mood) continue
    moodMap.set(row.mood, (moodMap.get(row.mood) ?? 0) + 1)
  }

  return Array.from(moodMap.entries())
    .map(([mood, count]) => ({ mood, count }))
    .sort((a, b) => b.count - a.count)
}

export async function getKeyDistribution(): Promise<KeyCount[]> {
  const supabase = await createClient()

  const [featuresResult, keysResult] = await Promise.all([
    supabase
      .from('track_audio_features_computed')
      .select('key_code')
      .not('key_code', 'is', null),
    supabase.from('keys').select('key_code, camelot'),
  ])

  if (!featuresResult.data || featuresResult.data.length === 0) return []

  const keyCodeMap = new Map<number, string>()
  if (keysResult.data) {
    for (const k of keysResult.data) {
      keyCodeMap.set(k.key_code, k.camelot)
    }
  }

  const countMap = new Map<number, number>()
  for (const row of featuresResult.data) {
    if (row.key_code === null || row.key_code === undefined) continue
    countMap.set(row.key_code, (countMap.get(row.key_code) ?? 0) + 1)
  }

  return Array.from(countMap.entries())
    .map(([key_code, count]) => ({
      camelot: keyCodeMap.get(key_code) ?? String(key_code),
      count,
    }))
    .sort((a, b) => b.count - a.count)
}

export async function getLufsDistribution(): Promise<LufsBin[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('integrated_lufs')
    .not('integrated_lufs', 'is', null)
    .gte('integrated_lufs', -30)
    .lte('integrated_lufs', 0)

  if (!data || data.length === 0) return []

  const lufsMap = new Map<number, number>()

  for (const row of data) {
    if (row.integrated_lufs === null || row.integrated_lufs === undefined) continue
    const rounded = Math.round(row.integrated_lufs)
    lufsMap.set(rounded, (lufsMap.get(rounded) ?? 0) + 1)
  }

  return Array.from(lufsMap.entries())
    .map(([lufs, count]) => ({ lufs, count }))
    .sort((a, b) => a.lufs - b.lufs)
}

export async function getAnalysisCoverage(): Promise<AnalysisLevelCount[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('analysis_level')

  if (!data || data.length === 0) return []

  const levelMap = new Map<number, number>()

  for (const row of data) {
    const level = row.analysis_level ?? 0
    levelMap.set(level, (levelMap.get(level) ?? 0) + 1)
  }

  return Array.from(levelMap.entries())
    .map(([level, count]) => ({ level, count }))
    .sort((a, b) => a.level - b.level)
}

export interface DanceabilityBin {
  bin: number
  count: number
}

export async function getDanceabilityDistribution(): Promise<DanceabilityBin[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('danceability')
    .not('danceability', 'is', null)

  if (!data || data.length === 0) return []

  const binMap = new Map<number, number>()

  for (const row of data) {
    if (row.danceability === null || row.danceability === undefined) continue
    const bin = Math.round((row.danceability as number) * 2) / 2
    binMap.set(bin, (binMap.get(bin) ?? 0) + 1)
  }

  return Array.from(binMap.entries())
    .map(([bin, count]) => ({ bin, count }))
    .sort((a, b) => a.bin - b.bin)
}

export interface HpRatioBin {
  bin: number
  count: number
}

export async function getHpRatioDistribution(): Promise<HpRatioBin[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('hp_ratio')
    .not('hp_ratio', 'is', null)

  if (!data || data.length === 0) return []

  const binMap = new Map<number, number>()

  for (const row of data) {
    if (row.hp_ratio === null || row.hp_ratio === undefined) continue
    const bin = Math.round(row.hp_ratio as number)
    binMap.set(bin, (binMap.get(bin) ?? 0) + 1)
  }

  return Array.from(binMap.entries())
    .map(([bin, count]) => ({ bin, count }))
    .sort((a, b) => a.bin - b.bin)
}

export interface PhraseCount {
  bars: number
  count: number
}

export async function getPhraseDistribution(): Promise<PhraseCount[]> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('dominant_phrase_bars')
    .not('dominant_phrase_bars', 'is', null)

  if (!data || data.length === 0) return []

  const groups = new Map<number, number>()

  for (const row of data) {
    if (row.dominant_phrase_bars === null || row.dominant_phrase_bars === undefined) continue
    const bars = row.dominant_phrase_bars as number
    groups.set(bars, (groups.get(bars) ?? 0) + 1)
  }

  return Array.from(groups.entries())
    .map(([bars, count]) => ({ bars, count }))
    .sort((a, b) => a.bars - b.bars)
}

export interface QualityFlags {
  variable_tempo_count: number
  atonality_count: number
  avg_bpm_confidence: number
}

export async function getQualityFlags(): Promise<QualityFlags> {
  const supabase = await createClient()

  const { data } = await supabase
    .from('track_audio_features_computed')
    .select('variable_tempo, atonality, bpm_confidence')

  if (!data || data.length === 0) {
    return { variable_tempo_count: 0, atonality_count: 0, avg_bpm_confidence: 0 }
  }

  const vt = data.filter((r) => r.variable_tempo === true).length
  const at = data.filter((r) => r.atonality === true).length
  const confs = data
    .filter((r) => r.bpm_confidence != null)
    .map((r) => r.bpm_confidence as number)
  const avgConf = confs.length > 0 ? confs.reduce((a, b) => a + b, 0) / confs.length : 0

  return { variable_tempo_count: vt, atonality_count: at, avg_bpm_confidence: avgConf }
}
