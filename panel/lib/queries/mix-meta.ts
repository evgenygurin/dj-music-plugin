import { createClient } from '@/lib/supabase/server'

export interface TrackSection {
  type: number // SectionType: 0 INTRO, 1 ATTACK, 2 BUILD, 3 PRE_DROP, 4 DROP,
  // 5 PEAK, 6 BREAKDOWN, 7 OUTRO, 8 RISE, 9 VALLEY, 10 SUSTAIN, 11 AMBIENT
  startMs: number
  endMs: number
  energy: number | null
  confidence: number | null
}

export interface TrackCuePoint {
  id: number
  positionMs: number
  kind: number // 0=cue, 1-7=hot cue 1-7
  hotcueIndex: number | null
  label: string | null
  color: string | null
}

export interface TrackMixMeta {
  trackId: number
  durationMs: number | null
  bpm: number | null
  firstDownbeatSec: number | null // best-effort: 0 if unknown
  outroStartSec: number | null // optimal mix-out start
  introEndSec: number | null // optimal end of mix-in zone
  introStartSec: number | null // start of intro (where to "drop" the next track in)
  sections: TrackSection[]
  cuePoints: TrackCuePoint[]
  // ── Loudness (for LUFS normalization during crossfade) ────
  integratedLufs: number | null
  truePeakDb: number | null
  // ── Kick / bass character (for adaptive bass swap) ────────
  kickProminence: number | null // 0..1 — how much the kick stands out
  hpRatio: number | null // harmonic-to-percussive ratio
  // ── Low-band energy (for swap-depth adaptation) ───────────
  energySub: number | null // ~20-60 Hz
  energyLow: number | null // ~60-250 Hz
  energyLowmid: number | null // ~250-500 Hz (kick click region)
}

const SECTION_INTRO = 0
const SECTION_OUTRO = 7

/** Fetches everything we need to plan a DJ-style transition for one track. */
export async function getTrackMixMeta(trackId: number): Promise<TrackMixMeta | null> {
  const supabase = await createClient()

  // Four parallel fetches. Beatgrid is a 2-step join through
  // `dj_library_items` because `dj_beatgrids.library_item_id` points
  // at library items, not tracks directly. We pick the canonical row
  // (tracks may have multiple beatgrid attempts) and fall back to
  // max(created_at) when nothing is flagged canonical.
  const [trackResult, featuresResult, sectionsResult, libraryItemResult, cueResult] =
    await Promise.all([
      supabase.from('tracks').select('id, duration_ms').eq('id', trackId).maybeSingle(),
      supabase
        .from('track_audio_features_computed')
        .select(
          'bpm, integrated_lufs, true_peak_db, kick_prominence, hp_ratio, energy_sub, energy_low, energy_lowmid, first_downbeat_ms',
        )
        .eq('track_id', trackId)
        .maybeSingle(),
      supabase
        .from('track_sections')
        .select('section_type, start_ms, end_ms, energy, confidence')
        .eq('track_id', trackId)
        .order('start_ms', { ascending: true }),
      supabase
        .from('dj_library_items')
        .select('id')
        .eq('track_id', trackId)
        .order('id', { ascending: true })
        .limit(1)
        .maybeSingle(),
      supabase
        .from('dj_cue_points')
        .select('id, position_ms, kind, hotcue_index, label, color')
        .eq('track_id', trackId)
        .order('position_ms', { ascending: true }),
    ])

  if (!trackResult.data) return null

  // Beatgrid is best-effort: if the library item exists we try to
  // pull the canonical grid, else fall back to the latest one. Any
  // failure silently leaves the fields as null and the crossfade
  // engine keeps its "firstDownbeat = 0" assumption.
  let beatgridBpm: number | null = null
  let firstDownbeatMs: number | null = null
  if (libraryItemResult.data?.id) {
    // Try canonical first.
    const canonical = await supabase
      .from('dj_beatgrids')
      .select('bpm, first_downbeat_ms, grid_offset_ms, canonical')
      .eq('library_item_id', libraryItemResult.data.id)
      .eq('canonical', true)
      .maybeSingle()
    let row = canonical.data
    if (!row) {
      // Fall back to any beatgrid — most recent first.
      const latest = await supabase
        .from('dj_beatgrids')
        .select('bpm, first_downbeat_ms, grid_offset_ms, canonical')
        .eq('library_item_id', libraryItemResult.data.id)
        .order('id', { ascending: false })
        .limit(1)
        .maybeSingle()
      row = latest.data ?? null
    }
    if (row) {
      beatgridBpm = typeof row.bpm === 'number' ? row.bpm : null
      // grid_offset_ms is an alternate name some importers use for
      // the same quantity (distance from sample 0 to first downbeat).
      // Prefer first_downbeat_ms, fall back to grid_offset_ms.
      firstDownbeatMs =
        typeof row.first_downbeat_ms === 'number'
          ? row.first_downbeat_ms
          : typeof row.grid_offset_ms === 'number'
            ? row.grid_offset_ms
            : null
    }
  }

  const sections: TrackSection[] = (sectionsResult.data ?? []).map((s) => ({
    type: s.section_type,
    startMs: s.start_ms,
    endMs: s.end_ms,
    energy: s.energy,
    confidence: s.confidence,
  }))

  // Pick the LAST outro section as the mix-out anchor (some tracks have a brief
  // intro-style outro plus a real outro further on).
  const outros = sections.filter((s) => s.type === SECTION_OUTRO)
  const outroStart = outros.length ? outros[outros.length - 1].startMs : null

  // Intro: prefer the FIRST intro for both bounds.
  const intros = sections.filter((s) => s.type === SECTION_INTRO)
  const introStart = intros.length ? intros[0].startMs : null
  const introEnd = intros.length ? intros[0].endMs : null

  const features = featuresResult.data
  const pickNumber = (v: unknown): number | null =>
    typeof v === 'number' && Number.isFinite(v) ? v : null

  return {
    trackId,
    durationMs: trackResult.data.duration_ms,
    // Prefer beatgrid BPM (measured on the audio itself) over the
    // features row, which may come from a different analyzer pass.
    // Both are reliable for techno but the beatgrid is what the
    // downbeat math uses, so use the same source for both.
    bpm: beatgridBpm ?? pickNumber(features?.bpm),
    // Prefer first_downbeat_ms from features (populated by pipeline beat
    // detection), then beatgrid, then compute on-the-fly via backend.
    // TODO: Remove on-the-fly computation after beatgrid migration completes
    // and all tracks have first_downbeat_ms populated in DB.
    firstDownbeatSec: await (async () => {
      const fromFeatures = pickNumber(features?.first_downbeat_ms)
      if (fromFeatures != null) return fromFeatures / 1000
      if (firstDownbeatMs != null) return firstDownbeatMs / 1000
      // On-the-fly: ask backend to compute and cache
      try {
        const REST_BASE = (process.env.MCP_HTTP_URL ?? 'http://localhost:8001')
          .replace(/\/+mcp\/?$/, '').replace(/\/+$/, '')
        const r = await fetch(`${REST_BASE}/api/audio/downbeat/${trackId}`, {
          cache: 'no-store',
          signal: AbortSignal.timeout(10_000),
        })
        if (r.ok) {
          const d = await r.json()
          const ms = typeof d.first_downbeat_ms === 'number' ? d.first_downbeat_ms : 0
          return ms / 1000
        }
      } catch { /* ignore — fallback to 0 */ }
      return 0
    })(),
    outroStartSec: outroStart != null ? outroStart / 1000 : null,
    introEndSec: introEnd != null ? introEnd / 1000 : null,
    introStartSec: introStart != null ? introStart / 1000 : null,
    sections,
    cuePoints: (cueResult.data ?? []).map((c) => ({
      id: c.id as number,
      positionMs: c.position_ms as number,
      kind: c.kind as number,
      hotcueIndex: (c.hotcue_index as number | null) ?? null,
      label: (c.label as string | null) ?? null,
      color: (c.color as string | null) ?? null,
    })),
    integratedLufs: pickNumber(features?.integrated_lufs),
    truePeakDb: pickNumber(features?.true_peak_db),
    kickProminence: pickNumber(features?.kick_prominence),
    hpRatio: pickNumber(features?.hp_ratio),
    energySub: pickNumber(features?.energy_sub),
    energyLow: pickNumber(features?.energy_low),
    energyLowmid: pickNumber(features?.energy_lowmid),
  }
}
