'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import MinimapPlugin from 'wavesurfer.js/dist/plugins/minimap.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'

import { fetchTrackMixMeta } from '@/actions/mix-meta-actions'
import type { TrackSection } from '@/lib/queries/mix-meta'
import { cn } from '@/lib/utils'

const SECTION_COLORS: Record<number, string> = {
  0: 'rgba(56, 189, 248, 0.18)',
  1: 'rgba(250, 204, 21, 0.20)',
  2: 'rgba(251, 146, 60, 0.20)',
  3: 'rgba(244, 114, 182, 0.22)',
  4: 'rgba(232, 121, 249, 0.30)',
  5: 'rgba(217, 70, 239, 0.28)',
  6: 'rgba(99, 102, 241, 0.20)',
  7: 'rgba(45, 212, 191, 0.20)',
  8: 'rgba(253, 186, 116, 0.20)',
  9: 'rgba(148, 163, 184, 0.18)',
  10: 'rgba(132, 204, 22, 0.18)',
  11: 'rgba(165, 180, 252, 0.16)',
}

const SECTION_LABELS: Record<number, string> = {
  0: 'intro', 1: 'attack', 2: 'build', 3: 'pre-drop',
  4: 'drop', 5: 'peak', 6: 'breakdown', 7: 'outro',
  8: 'rise', 9: 'valley', 10: 'sustain', 11: 'ambient',
}

const EMPTY_SECTIONS: TrackSection[] = []

interface Props {
  trackId: number
  position: number
  duration: number
  onSeek: (seconds: number) => void
  className?: string
  height?: number
  /** Enable pinch-to-zoom, wheel zoom, auto-scroll */
  zoomable?: boolean
  /** Show minimap overview strip */
  showMinimap?: boolean
  /** Show time markers */
  showTimeline?: boolean
  /** Tap callback (for opening fullscreen) */
  onTap?: () => void
}

interface SectionsState {
  trackId: number | null
  values: TrackSection[]
}

export function TrackWaveform({
  trackId,
  position,
  duration,
  onSeek,
  className,
  height = 56,
  zoomable = false,
  showMinimap = false,
  showTimeline = false,
  onTap,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const wavesurferRef = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<ReturnType<typeof RegionsPlugin.create> | null>(null)
  const onSeekRef = useRef(onSeek)
  const zoomRef = useRef(zoomable ? 80 : 0)
  const pinchStartRef = useRef(0)
  const pinchZoomRef = useRef(80)
  const [sectionsState, setSectionsState] = useState<SectionsState>({ trackId: null, values: [] })
  const [readyTrackId, setReadyTrackId] = useState<number | null>(null)
  const sections = sectionsState.trackId === trackId ? sectionsState.values : EMPTY_SECTIONS
  const ready = readyTrackId === trackId

  useEffect(() => { onSeekRef.current = onSeek }, [onSeek])

  // Load sections
  useEffect(() => {
    let cancelled = false
    fetchTrackMixMeta(trackId).then(meta => {
      if (!cancelled) setSectionsState({ trackId, values: meta?.sections ?? [] })
    }).catch(() => undefined)
    return () => { cancelled = true }
  }, [trackId])

  // Create wavesurfer
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const regions = RegionsPlugin.create()
    const plugins: any[] = [regions]

    if (showMinimap) {
      plugins.push(MinimapPlugin.create({
        height: 20,
        waveColor: 'rgba(148, 163, 184, 0.2)',
        progressColor: 'rgba(148, 163, 184, 0.4)',
        insertPosition: 'beforebegin',
      }))
    }

    if (showTimeline) {
      plugins.push(TimelinePlugin.create({
        height: 16,
        style: { fontSize: '9px', color: 'rgba(148, 163, 184, 0.3)' },
        insertPosition: 'afterend',
      }))
    }

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
      backend: 'MediaElement',
      mediaControls: false,
      plugins,
      ...(zoomable ? {
        minPxPerSec: 80,
        autoScroll: true,
        autoCenter: true,
        hideScrollbar: true,
      } : {}),
    })

    wavesurferRef.current = ws
    regionsRef.current = regions
    zoomRef.current = zoomable ? 80 : 0

    const mediaEl = ws.getMediaElement()
    if (mediaEl) { mediaEl.muted = true; mediaEl.volume = 0 }

    ws.on('ready', () => setReadyTrackId(trackId))
    ws.on('interaction', (newTime: number) => {
      onSeekRef.current(newTime)
      try { ws.pause() } catch {}
    })

    void ws.load(`/api/audio/${trackId}`).catch(() => {})

    return () => {
      try { ws.destroy() } catch {}
      setReadyTrackId(cur => cur === trackId ? null : cur)
      wavesurferRef.current = null
      regionsRef.current = null
    }
  }, [trackId, height, zoomable, showMinimap, showTimeline])

  // Drive playhead
  useEffect(() => {
    const ws = wavesurferRef.current
    if (!ws || !ready) return
    try {
      if (Math.abs(ws.getCurrentTime() - position) > 0.05) ws.setTime(position)
    } catch {}
  }, [position, ready])

  // Draw section regions
  useEffect(() => {
    const regions = regionsRef.current
    if (!regions || !ready || sections.length === 0) return
    regions.clearRegions()
    for (const s of sections) {
      const start = s.startMs / 1000
      const end = s.endMs / 1000
      if (end <= start) continue
      regions.addRegion({
        start, end,
        color: SECTION_COLORS[s.type] ?? 'rgba(148, 163, 184, 0.15)',
        drag: false, resize: false,
        content: SECTION_LABELS[s.type] ?? '',
      })
    }
  }, [sections, ready])

  // Pinch-to-zoom (touch)
  useEffect(() => {
    if (!zoomable) return
    const el = containerRef.current
    if (!el) return

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX
        const dy = e.touches[0].clientY - e.touches[1].clientY
        pinchStartRef.current = Math.hypot(dx, dy)
        pinchZoomRef.current = zoomRef.current
      }
    }

    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length !== 2) return
      e.preventDefault()
      const dx = e.touches[0].clientX - e.touches[1].clientX
      const dy = e.touches[0].clientY - e.touches[1].clientY
      const dist = Math.hypot(dx, dy)
      const scale = dist / (pinchStartRef.current || 1)
      const newZoom = Math.max(20, Math.min(800, pinchZoomRef.current * scale))
      zoomRef.current = newZoom
      wavesurferRef.current?.zoom(newZoom)
    }

    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: false })
    return () => {
      el.removeEventListener('touchstart', onTouchStart)
      el.removeEventListener('touchmove', onTouchMove)
    }
  }, [zoomable])

  // Wheel zoom (desktop: Ctrl/Cmd + scroll)
  useEffect(() => {
    if (!zoomable) return
    const el = containerRef.current
    if (!el) return

    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      const factor = e.deltaY > 0 ? 0.85 : 1.18
      const newZoom = Math.max(20, Math.min(800, zoomRef.current * factor))
      zoomRef.current = newZoom
      wavesurferRef.current?.zoom(newZoom)
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomable])

  const progressPct = duration > 0 ? Math.min(100, (position / duration) * 100) : 0

  return (
    <div
      className={cn('relative w-full', zoomable && 'touch-none', className)}
      style={{ height: showMinimap ? height + 24 : showTimeline ? height + 20 : height }}
      onClick={onTap}
    >
      <div ref={containerRef} className="absolute inset-0" />
      {ready ? null : (
        <div className="pointer-events-none absolute inset-0 flex items-center px-1" aria-hidden>
          <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full bg-primary/60 transition-[width] duration-150" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}
