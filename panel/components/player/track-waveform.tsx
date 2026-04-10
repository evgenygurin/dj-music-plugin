'use client'

import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'

import { fetchTrackMixMeta } from '@/actions/mix-meta-actions'
import type { TrackSection } from '@/lib/queries/mix-meta'
import { cn } from '@/lib/utils'

/**
 * 12-color palette for SectionType (must match `app/core/constants.py`):
 *   0 INTRO, 1 ATTACK, 2 BUILD, 3 PRE_DROP, 4 DROP, 5 PEAK,
 *   6 BREAKDOWN, 7 OUTRO, 8 RISE, 9 VALLEY, 10 SUSTAIN, 11 AMBIENT
 *
 * Hues are picked so adjacent low/high-energy sections are visually distinct
 * and the palette stays inside the panel's cyberpunk neon vocabulary.
 */
const SECTION_COLORS: Record<number, string> = {
  0: 'rgba(56, 189, 248, 0.18)', // INTRO — cyan
  1: 'rgba(250, 204, 21, 0.20)', // ATTACK — yellow
  2: 'rgba(251, 146, 60, 0.20)', // BUILD — orange
  3: 'rgba(244, 114, 182, 0.22)', // PRE_DROP — pink
  4: 'rgba(232, 121, 249, 0.30)', // DROP — magenta
  5: 'rgba(217, 70, 239, 0.28)', // PEAK — bright magenta
  6: 'rgba(99, 102, 241, 0.20)', // BREAKDOWN — indigo
  7: 'rgba(45, 212, 191, 0.20)', // OUTRO — teal
  8: 'rgba(253, 186, 116, 0.20)', // RISE — soft orange
  9: 'rgba(148, 163, 184, 0.18)', // VALLEY — slate
  10: 'rgba(132, 204, 22, 0.18)', // SUSTAIN — lime
  11: 'rgba(165, 180, 252, 0.16)', // AMBIENT — soft indigo
}

const SECTION_LABELS: Record<number, string> = {
  0: 'intro',
  1: 'attack',
  2: 'build',
  3: 'pre-drop',
  4: 'drop',
  5: 'peak',
  6: 'breakdown',
  7: 'outro',
  8: 'rise',
  9: 'valley',
  10: 'sustain',
  11: 'ambient',
}

const EMPTY_SECTIONS: TrackSection[] = []

interface Props {
  trackId: number
  position: number // seconds (driven by external AudioPlayer)
  duration: number // seconds
  onSeek: (seconds: number) => void
  className?: string
  height?: number
}

interface SectionsState {
  trackId: number | null
  values: TrackSection[]
}

/**
 * Visualization-only waveform driven by an external audio engine.
 *
 * Wavesurfer creates its own HTMLAudioElement to fetch and decode peaks,
 * but we mute it (volume=0) and never call `play()`. The playhead is
 * driven from the outside via `position` prop, and seeks bubble back up
 * through `onSeek`. The real audio comes from the AudioPlayer context's
 * Web Audio decks.
 *
 * Sections are loaded asynchronously via `fetchTrackMixMeta` and rendered
 * as colored regions on top of the waveform.
 */
export function TrackWaveform({
  trackId,
  position,
  duration,
  onSeek,
  className,
  height = 56,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<ReturnType<typeof RegionsPlugin.create> | null>(null)
  const onSeekRef = useRef(onSeek)
  const [sectionsState, setSectionsState] = useState<SectionsState>({
    trackId: null,
    values: [],
  })
  const [readyTrackId, setReadyTrackId] = useState<number | null>(null)
  const sections =
    sectionsState.trackId === trackId ? sectionsState.values : EMPTY_SECTIONS
  const ready = readyTrackId === trackId

  useEffect(() => {
    onSeekRef.current = onSeek
  }, [onSeek])

  // Load section metadata whenever the track changes.
  useEffect(() => {
    let cancelled = false
    fetchTrackMixMeta(trackId)
      .then((meta) => {
        if (cancelled) return
        setSectionsState({
          trackId,
          values: meta?.sections ?? [],
        })
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [trackId])

  // Create the wavesurfer instance once the container exists, then load
  // the audio file for peak generation. Recreated when trackId changes.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const regions = RegionsPlugin.create()
    const ws = WaveSurfer.create({
      container: el,
      height,
      waveColor: 'rgba(148, 163, 184, 0.45)',
      progressColor: 'rgba(232, 121, 249, 0.85)',
      cursorColor: 'rgba(232, 121, 249, 1)',
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 1,
      normalize: true,
      interact: true,
      // We never call play() — wavesurfer's audio element exists only to
      // decode peaks. Mute it just in case some browser auto-resumes.
      backend: 'MediaElement',
      mediaControls: false,
      plugins: [regions],
    })
    wavesurferRef.current = ws
    regionsRef.current = regions

    // Mute the internal audio element to guarantee it never makes sound,
    // even if interact triggers a play() under the hood.
    const mediaEl = ws.getMediaElement()
    if (mediaEl) {
      mediaEl.muted = true
      mediaEl.volume = 0
    }

    ws.on('ready', () => {
      setReadyTrackId(trackId)
    })

    ws.on('interaction', (newTime: number) => {
      onSeekRef.current(newTime)
      // Pause wavesurfer's internal media in case interaction started it.
      try {
        ws.pause()
      } catch {
        // ignore
      }
    })

    void ws.load(`/api/audio/${trackId}`).catch(() => {
      // network/decoding failures are non-fatal — the waveform just stays empty
    })

    return () => {
      try {
        ws.destroy()
      } catch {
        // ignore
      }
      setReadyTrackId((current) => (current === trackId ? null : current))
      wavesurferRef.current = null
      regionsRef.current = null
    }
  }, [trackId, height])

  // Drive the playhead from the external position prop.
  useEffect(() => {
    const ws = wavesurferRef.current
    if (!ws || !ready) return
    try {
      // Avoid fighting wavesurfer when the user is scrubbing — only push
      // when the delta is significant. setTime is cheap enough at 30fps.
      const wsTime = ws.getCurrentTime()
      if (Math.abs(wsTime - position) > 0.05) {
        ws.setTime(position)
      }
    } catch {
      // ignore
    }
  }, [position, ready])

  // (Re)draw section regions whenever sections or readiness change.
  useEffect(() => {
    const regions = regionsRef.current
    if (!regions || !ready || sections.length === 0) return
    regions.clearRegions()
    for (const s of sections) {
      const start = s.startMs / 1000
      const end = s.endMs / 1000
      if (end <= start) continue
      regions.addRegion({
        start,
        end,
        color: SECTION_COLORS[s.type] ?? 'rgba(148, 163, 184, 0.15)',
        drag: false,
        resize: false,
        content: SECTION_LABELS[s.type] ?? '',
      })
    }
  }, [sections, ready])

  // Fallback bar shown until peaks are decoded — keeps layout height stable
  // and gives the user *some* visual feedback during the first ~200ms.
  const progressPct =
    duration > 0 ? Math.min(100, (position / duration) * 100) : 0

  return (
    <div className={cn('relative w-full', className)} style={{ height }}>
      <div ref={containerRef} className="absolute inset-0" />
      {ready ? null : (
        <div
          className="pointer-events-none absolute inset-0 flex items-center px-1"
          aria-hidden
        >
          <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary/60 transition-[width] duration-150"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
