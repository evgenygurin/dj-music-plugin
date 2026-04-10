import { cache } from 'react'
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

interface DashboardFeatureRow {
  bpm: number | null
  mood: string | null
  key_code: number | null
  integrated_lufs: number | null
  analysis_level: number | null
  danceability: number | null
  hp_ratio: number | null
  dominant_phrase_bars: number | null
  variable_tempo: boolean | null
  atonality: boolean | null
  bpm_confidence: number | null
}

const getDashboardFeatureRows = cache(async (): Promise<DashboardFeatureRow[]> => {
  const supabase = await createClient()
  const { data, error } = await supabase.from('track_audio_features_computed').select(
    'bpm, mood, key_code, integrated_lufs, analysis_level, danceability, hp_ratio, dominant_phrase_bars, variable_tempo, atonality, bpm_confidence'
  )

  if (error) throw error
  return data ?? []
})

const getKeyLookup = cache(async (): Promise<Map<number, string>> => {
  const supabase = await createClient()
  const { data, error } = await supabase.from('keys').select('key_code, camelot')

  if (error) throw error

  const keyMap = new Map<number, string>()
  for (const item of data ?? []) {
    keyMap.set(item.key_code, item.camelot)
  }
  return keyMap
})

const getSetQualityScores = cache(async (): Promise<number[]> => {
  const supabase = await createClient()
  const { data, error } = await supabase.from('dj_set_versions').select('quality_score')

  if (error) throw error

  return (data ?? [])
    .map((version) => version.quality_score)
    .filter((score): score is number => score !== null && score !== undefined)
})

export async function getLibraryStats(): Promise<LibraryStats> {
  const supabase = await createClient()
  const [features, qualityScores] = await Promise.all([
    getDashboardFeatureRows(),
    getSetQualityScores(),
  ])

  const [tracksResult, setsResult, libraryResult] =
    await Promise.all([
      supabase.from('tracks').select('*', { count: 'exact', head: true }),
      supabase.from('dj_sets').select('*', { count: 'exact', head: true }),
      supabase.from('dj_library_items').select('*', { count: 'exact', head: true }),
    ])

  const avgSetQuality =
    qualityScores.length > 0
      ? qualityScores.reduce((sum, score) => sum + score, 0) / qualityScores.length
      : null

  return {
    totalTracks: tracksResult.count ?? 0,
    analyzedTracks: features.filter((row) => row.bpm !== null).length,
    totalSets: setsResult.count ?? 0,
    libraryItems: libraryResult.count ?? 0,
    avgSetQuality,
  }
}

export async function getBpmDistribution(): Promise<BpmBin[]> {
  const data = (await getDashboardFeatureRows()).filter(
    (row) => row.bpm !== null && row.bpm >= 80 && row.bpm <= 200
  )

  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()
  if (data.length === 0) return []

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
  const [features, keyCodeMap] = await Promise.all([
    getDashboardFeatureRows(),
    getKeyLookup(),
  ])

  if (features.length === 0) return []

  const countMap = new Map<number, number>()
  for (const row of features) {
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
  const data = (await getDashboardFeatureRows()).filter(
    (row) => row.integrated_lufs !== null && row.integrated_lufs >= -30 && row.integrated_lufs <= 0
  )

  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()
  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()
  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()
  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()
  if (data.length === 0) return []

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
  const data = await getDashboardFeatureRows()

  if (data.length === 0) {
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
