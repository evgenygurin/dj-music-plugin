import { createClient } from '@/lib/supabase/server'

export interface TrackSection {
  type: number // SectionType: 0 INTRO, 1 ATTACK, 2 BUILD, 3 PRE_DROP, 4 DROP,
  // 5 PEAK, 6 BREAKDOWN, 7 OUTRO, 8 RISE, 9 VALLEY, 10 SUSTAIN, 11 AMBIENT
  startMs: number
  endMs: number
  energy: number | null
  confidence: number | null
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
}

const SECTION_INTRO = 0
const SECTION_OUTRO = 7

/** Fetches everything we need to plan a DJ-style transition for one track. */
export async function getTrackMixMeta(trackId: number): Promise<TrackMixMeta | null> {
  const supabase = await createClient()

  const [trackResult, featuresResult, sectionsResult] = await Promise.all([
    supabase.from('tracks').select('id, duration_ms').eq('id', trackId).maybeSingle(),
    supabase
      .from('track_audio_features_computed')
      .select('bpm')
      .eq('track_id', trackId)
      .maybeSingle(),
    supabase
      .from('track_sections')
      .select('section_type, start_ms, end_ms, energy, confidence')
      .eq('track_id', trackId)
      .order('start_ms', { ascending: true }),
  ])

  if (!trackResult.data) return null

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

  return {
    trackId,
    durationMs: trackResult.data.duration_ms,
    bpm: featuresResult.data?.bpm ?? null,
    firstDownbeatSec: 0, // unknown without beatgrid; assumed 0 for techno
    outroStartSec: outroStart != null ? outroStart / 1000 : null,
    introEndSec: introEnd != null ? introEnd / 1000 : null,
    introStartSec: introStart != null ? introStart / 1000 : null,
    sections,
  }
}
