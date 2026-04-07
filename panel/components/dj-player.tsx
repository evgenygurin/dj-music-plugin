'use client'

import { useMemo, useRef, useState, useCallback, useEffect } from 'react'
import { useRouter, usePathname, useSearchParams } from 'next/navigation'
import { Search } from 'lucide-react'
import {
  IconPlayerPlay,
  IconPlayerPause,
  IconArrowLeft,
  IconArrowRight,
  IconRepeat,
  IconMusic,
} from '@tabler/icons-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { MoodBadge } from '@/components/mood-badge'
import { cn, formatBpm, formatDuration, formatLufs } from '@/lib/utils'
import type { TrackDetail, TrackRow } from '@/lib/queries/tracks'

// ─── Constants ─────────────────────────────────────────────────────────────

const SECTION_COLORS: Record<number, string> = {
  0: '#64748b', 1: '#3b82f6', 2: '#06b6d4', 3: '#10b981',
  4: '#84cc16', 5: '#f59e0b', 6: '#8b5cf6', 7: '#6b7280',
  8: '#22d3ee', 9: '#475569', 10: '#94a3b8',
}

const SECTION_LABELS: Record<number, string> = {
  0: 'Intro', 1: 'Attack', 2: 'Build', 3: 'Pre-Drop',
  4: 'Drop', 5: 'Peak', 6: 'Breakdown', 7: 'Outro',
  8: 'Rise', 9: 'Valley', 10: 'Sustain',
}

const CUE_COLORS: Record<number, string> = {
  0: '#ffffff',
  1: '#f97316', 2: '#22c55e', 3: '#3b82f6', 4: '#a855f7',
  5: '#ec4899', 6: '#eab308', 7: '#f43f5e',
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function pseudoRandom(seed: number, index: number): number {
  const x = Math.sin(seed * 9301 + index * 49297 + 233280) * 10000
  return x - Math.floor(x)
}

// ─── Waveform ──────────────────────────────────────────────────────────────

function Waveform({
  trackId,
  sections,
  cuePoints,
  duration_ms,
  color,
  height = 52,
}: {
  trackId: number
  sections: TrackDetail['sections']
  cuePoints: TrackDetail['cuePoints']
  duration_ms: number | null
  color: string
  height?: number
}) {
  const N = 120
  const bars = useMemo(
    () =>
      Array.from({ length: N }, (_, i) => {
        const b = pseudoRandom(trackId, i)
        const p = i > 0 ? pseudoRandom(trackId, i - 1) : b
        const n = i < N - 1 ? pseudoRandom(trackId, i + 1) : b
        return 0.12 + (b * 0.5 + p * 0.25 + n * 0.25) * 0.88
      }),
    [trackId]
  )

  const barColor = (i: number) => {
    if (!sections.length || !duration_ms) return color
    const ms = (i / N) * duration_ms
    const sec = sections.find((s) => ms >= s.start_ms && ms < s.end_ms)
    return sec ? (SECTION_COLORS[sec.section_type] ?? color) : color
  }

  return (
    <div className="relative w-full overflow-hidden rounded" style={{ height }}>
      <div className="absolute inset-0 bg-black/60" />

      {/* Section tints */}
      {sections.map((s) => {
        if (!duration_ms) return null
        const left = (s.start_ms / duration_ms) * 100
        const width = ((s.end_ms - s.start_ms) / duration_ms) * 100
        return (
          <Tooltip key={s.id}>
            <TooltipTrigger asChild>
              <div
                className="absolute top-0 bottom-0 opacity-10 cursor-default"
                style={{ left: `${left}%`, width: `${width}%`, background: SECTION_COLORS[s.section_type] }}
              />
            </TooltipTrigger>
            <TooltipContent side="top">
              <span>{SECTION_LABELS[s.section_type]}</span>
              {s.energy !== null && (
                <span className="ml-1 text-muted-foreground">
                  {(s.energy * 100).toFixed(0)}%
                </span>
              )}
            </TooltipContent>
          </Tooltip>
        )
      })}

      {/* Bars */}
      <div className="absolute inset-x-0 bottom-0 flex items-end gap-px px-0.5" style={{ height: '100%' }}>
        {bars.map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-t-sm opacity-70"
            style={{ height: `${h * 100}%`, background: barColor(i), minWidth: 1 }}
          />
        ))}
      </div>

      {/* Cue markers */}
      {cuePoints.map((cue) => {
        if (!duration_ms) return null
        const left = (cue.position_ms / duration_ms) * 100
        const col = CUE_COLORS[cue.kind] ?? '#fff'
        return (
          <Tooltip key={cue.id}>
            <TooltipTrigger asChild>
              <div
                className="absolute top-0 bottom-0 w-0.5 cursor-default"
                style={{ left: `${left}%`, background: col }}
              />
            </TooltipTrigger>
            <TooltipContent side="top">
              {cue.label ?? `Cue ${cue.hotcue_index ?? ''}`}
            </TooltipContent>
          </Tooltip>
        )
      })}

      {/* Playhead */}
      <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white/90 pointer-events-none" />
    </div>
  )
}

// ─── Jump bar ──────────────────────────────────────────────────────────────

function JumpBar({ trackId, color }: { trackId: number; color: string }) {
  const bars = useMemo(
    () => Array.from({ length: 200 }, (_, i) => 0.1 + pseudoRandom(trackId + 1, i) * 0.9),
    [trackId]
  )
  return (
    <div className="relative w-full overflow-hidden rounded-sm" style={{ height: 18 }}>
      <div className="absolute inset-0 bg-black/50" />
      <div className="absolute inset-x-0 bottom-0 flex items-end gap-px" style={{ height: '100%' }}>
        {bars.map((h, i) => (
          <div key={i} className="flex-1" style={{ height: `${h * 100}%`, background: color, opacity: 0.35, minWidth: 1 }} />
        ))}
      </div>
      <div className="absolute inset-y-0 left-0 w-1/2 bg-white/5" />
      <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white" />
    </div>
  )
}

// ─── EQ Knob ───────────────────────────────────────────────────────────────

function EqKnob({ label }: { label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col items-center gap-0.5 cursor-default">
          <div className="relative flex items-center justify-center rounded-full border border-white/20 bg-[#1a1a1c]" style={{ width: 26, height: 26 }}>
            <div className="absolute w-1 h-1 rounded-full bg-white/70" style={{ top: 4, left: '50%', transform: 'translateX(-50%)' }} />
          </div>
          <span className="text-[9px] text-muted-foreground font-mono">{label}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label} EQ</TooltipContent>
    </Tooltip>
  )
}

// ─── VU Meter ─────────────────────────────────────────────────────────────

function VuMeter({ lufs }: { lufs: number | null }) {
  const pct = lufs !== null ? Math.max(0, Math.min(100, ((lufs + 20) / 16) * 100)) : 0
  const col = pct > 85 ? '#ef4444' : pct > 65 ? '#f59e0b' : '#4ade80'
  return (
    <div className="flex gap-px" style={{ width: 8, height: 110 }}>
      {[0, 1].map((ch) => (
        <div key={ch} className="flex-1 flex flex-col-reverse rounded-sm overflow-hidden bg-black/40">
          <div className="rounded-sm" style={{ height: `${pct}%`, background: col }} />
        </div>
      ))}
    </div>
  )
}

// ─── Hot Cues ─────────────────────────────────────────────────────────────

function HotCueGrid({ cuePoints }: { cuePoints: TrackDetail['cuePoints'] }) {
  const slots = Array.from({ length: 8 }, (_, i) => ({
    index: i + 1,
    cue: cuePoints.find((c) => c.hotcue_index === i + 1),
  }))
  return (
    <div className="grid grid-cols-4 gap-1">
      {slots.map(({ index, cue }) => {
        const col = cue ? (CUE_COLORS[cue.kind] ?? '#fff') : undefined
        const btn = (
          <div
            key={index}
            className="flex items-center justify-center rounded text-xs font-mono font-semibold select-none cursor-default"
            style={{
              width: 22, height: 22,
              background: col ? col + '25' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${col ? col + '70' : 'rgba(255,255,255,0.08)'}`,
              color: col ?? 'rgba(255,255,255,0.25)',
            }}
          >
            {index}
          </div>
        )
        return cue ? (
          <Tooltip key={index}>
            <TooltipTrigger asChild>{btn}</TooltipTrigger>
            <TooltipContent side="top">
              {cue.label ?? `Hot cue ${index}`}
              <span className="ml-1 text-muted-foreground font-mono">
                {formatDuration(cue.position_ms)}
              </span>
            </TooltipContent>
          </Tooltip>
        ) : btn
      })}
    </div>
  )
}

// ─── Pitch Slider (vertical) ───────────────────────────────────────────────

function PitchSlider({ color }: { color: string }) {
  const [val, setVal] = useState([50])
  const pct = ((val[0] - 50) / 50 * 8).toFixed(1) // ±8%
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex flex-col items-center gap-1" style={{ height: 110 }}>
          <Slider
            orientation="vertical"
            min={0} max={100}
            value={val}
            onValueChange={setVal}
            className="flex-1"
            style={{ '--slider-color': color } as React.CSSProperties}
          />
          <span className="text-[9px] font-mono text-muted-foreground tabular-nums w-10 text-center">
            {val[0] === 50 ? '±0.0%' : `${Number(pct) > 0 ? '+' : ''}${pct}%`}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="right">Pitch ±8%</TooltipContent>
    </Tooltip>
  )
}

// ─── Deck ──────────────────────────────────────────────────────────────────

function Deck({
  side,
  track,
  isPlaying,
  onTogglePlay,
}: {
  side: 'A' | 'B'
  track: TrackDetail | null
  isPlaying: boolean
  onTogglePlay: () => void
}) {
  const isA = side === 'A'
  const color = isA ? '#22d3ee' : '#e879f9'
  const borderCls = isA ? 'border-cyan-500/25' : 'border-fuchsia-500/25'
  const accentCls = isA ? 'text-cyan-400' : 'text-fuchsia-400'

  const bpm = track?.features?.bpm ?? null
  const camelot = track?.features?.camelot ?? null
  const lufs = track?.features?.integrated_lufs ?? null
  const energy = track?.features?.energy_mean ?? null
  const mood = track?.features?.mood ?? null
  const duration = track?.duration_ms ?? null
  const artists = track?.artists.map((a) => a.name).join(', ') ?? ''

  return (
    <Card className={cn('gap-2 py-3 border bg-[#0a0a0c]', borderCls)}>
      <CardContent className="px-3 flex flex-col gap-2">

        {/* Header */}
        <div className="flex items-start gap-2">
          <div
            className="shrink-0 flex items-center justify-center rounded text-[10px] font-bold"
            style={{ width: 22, height: 22, background: color + '18', color, border: `1px solid ${color}40` }}
          >
            {side}
          </div>
          <div
            className="shrink-0 rounded flex items-center justify-center bg-black/40"
            style={{ width: 34, height: 34, border: `1px solid ${color}18` }}
          >
            <IconMusic className="text-muted-foreground" style={{ width: 14, height: 14 }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="truncate text-sm font-semibold leading-tight">
              {track?.title ?? <span className="text-muted-foreground text-xs italic">Load Track...</span>}
            </div>
            {artists && <div className="truncate text-xs text-muted-foreground">{artists}</div>}
          </div>
          <div className="shrink-0 text-right">
            <div className={cn('text-xs font-mono font-bold tabular-nums', accentCls)}>0:00</div>
            <div className="text-[10px] text-muted-foreground font-mono tabular-nums">
              {duration ? formatDuration(duration) : '—:——'}
            </div>
          </div>
        </div>

        {/* Badges row */}
        <div className="flex items-center gap-1.5 flex-wrap min-h-5">
          {camelot && (
            <Badge variant="outline" className={cn('text-[10px] px-1 py-0 h-4 font-mono', accentCls)}>
              {camelot}
            </Badge>
          )}
          {mood && <MoodBadge mood={mood} />}
          {lufs !== null && (
            <span className="text-[10px] text-muted-foreground font-mono">{formatLufs(lufs)}</span>
          )}
        </div>

        {/* Jump bar */}
        {track
          ? <JumpBar trackId={track.id} color={color} />
          : <div className="w-full rounded-sm bg-black/30" style={{ height: 18 }} />}

        {/* Main waveform */}
        {track ? (
          <Waveform
            trackId={track.id}
            sections={track.sections}
            cuePoints={track.cuePoints}
            duration_ms={duration}
            color={color}
          />
        ) : (
          <div className="w-full rounded bg-black/40 flex items-center justify-center" style={{ height: 52 }}>
            <span className="text-[10px] text-muted-foreground italic">No track loaded</span>
          </div>
        )}

        {/* Controls: vinyl + hot cues + EQ + VU + Pitch */}
        <div className="flex items-start gap-3">
          {/* Vinyl */}
          <div
            className="shrink-0 rounded-full relative flex items-center justify-center"
            style={{ width: 60, height: 60, background: '#0a0a0c', border: `2px solid ${color}28` }}
          >
            <div
              className="absolute inset-0 rounded-full"
              style={{ background: `conic-gradient(from 0deg, ${color}08, ${color}28, ${color}06, ${color}22, ${color}08)` }}
            />
            <div className="absolute inset-[5px] rounded-full bg-[#171719]" />
            <div className="absolute inset-[20px] rounded-full" style={{ background: color + '35' }} />
            <div className="absolute inset-[26px] rounded-full bg-white/15" />
          </div>

          {/* Hot cues */}
          <HotCueGrid cuePoints={track?.cuePoints ?? []} />

          {/* EQ */}
          <div className="flex gap-1.5 items-start pt-0.5">
            <EqKnob label="HI" />
            <EqKnob label="MID" />
            <EqKnob label="LO" />
          </div>

          {/* VU + Fader */}
          <div className="ml-auto flex items-end gap-1.5">
            <VuMeter lufs={lufs} />
            <Slider
              orientation="vertical"
              min={0} max={100}
              defaultValue={[80]}
              className="h-[110px] w-3"
            />
          </div>

          {/* Pitch */}
          <PitchSlider color={color} />
        </div>

        {/* BPM row */}
        <div className="flex items-baseline gap-2">
          <span className={cn('text-2xl font-bold tabular-nums font-mono leading-none', accentCls)}>
            {bpm !== null ? formatBpm(bpm) : '---.-'}
          </span>
          <span className="text-xs text-muted-foreground font-mono">BPM</span>
          {energy !== null && (
            <>
              <div className="flex-1 h-1 rounded-full bg-black/40 overflow-hidden ml-2">
                <div className="h-full rounded-full" style={{ width: `${energy * 100}%`, background: color }} />
              </div>
              <span className="text-[10px] text-muted-foreground font-mono tabular-nums">{energy.toFixed(3)}</span>
            </>
          )}
        </div>

        {/* Loop + Jump */}
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="rounded p-1 bg-white/5 border border-white/10 hover:bg-white/10">
                <IconArrowLeft className="size-3 text-muted-foreground" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Jump back</TooltipContent>
          </Tooltip>
          <button className="flex items-center gap-1 rounded px-2 py-0.5 text-xs bg-white/5 border border-white/10 hover:bg-white/10">
            <IconRepeat className="size-3" />
            <span className="font-mono">8</span>
          </button>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="rounded p-1 bg-white/5 border border-white/10 hover:bg-white/10">
                <IconArrowRight className="size-3 text-muted-foreground" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Jump forward</TooltipContent>
          </Tooltip>
        </div>

        {/* CUE + PLAY */}
        <div className="flex gap-2">
          <button
            className={cn(
              'flex-1 rounded py-1.5 text-xs font-semibold border transition-colors',
              isA
                ? 'border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/10'
                : 'border-fuchsia-500/40 text-fuchsia-400 hover:bg-fuchsia-500/10'
            )}
          >
            CUE
          </button>
          <button
            onClick={onTogglePlay}
            className={cn(
              'flex-1 rounded py-1.5 flex items-center justify-center gap-1.5 text-xs font-semibold transition-colors',
              isPlaying
                ? isA ? 'bg-cyan-500 text-black hover:bg-cyan-400' : 'bg-fuchsia-500 text-black hover:bg-fuchsia-400'
                : 'bg-white/10 text-white hover:bg-white/20'
            )}
          >
            {isPlaying ? <IconPlayerPause className="size-3.5" /> : <IconPlayerPlay className="size-3.5" />}
            {isPlaying ? 'PAUSE' : 'PLAY'}
          </button>
        </div>

      </CardContent>
    </Card>
  )
}

// ─── Mixer ────────────────────────────────────────────────────────────────

function Mixer({
  deck1,
  deck2,
  crossfader,
  onCrossfaderChange,
  sync1,
  sync2,
  onToggleSync1,
  onToggleSync2,
}: {
  deck1: TrackDetail | null
  deck2: TrackDetail | null
  crossfader: number
  onCrossfaderChange: (v: number) => void
  sync1: boolean
  sync2: boolean
  onToggleSync1: () => void
  onToggleSync2: () => void
}) {
  const bpm1 = deck1?.features?.bpm ?? null
  const bpm2 = deck2?.features?.bpm ?? null
  const masterBpm = sync1 ? bpm1 : sync2 ? bpm2 : bpm1

  return (
    <Card className="gap-2 py-3 border border-white/10 bg-[#0a0a0c]">
      <CardContent className="px-3 flex flex-col items-center gap-3">

        {/* Sync A */}
        <button
          onClick={onToggleSync1}
          className={cn(
            'w-full rounded text-xs font-semibold py-1 border transition-colors',
            sync1
              ? 'bg-cyan-500 text-black border-cyan-500'
              : 'border-cyan-500/30 text-cyan-400/50 hover:text-cyan-400 hover:border-cyan-500/60'
          )}
        >
          SYNC A
        </button>

        {/* BPM */}
        <div className="flex flex-col items-center gap-0.5 w-full">
          <span className="text-[9px] text-muted-foreground tracking-widest">MASTER</span>
          <span className="text-xl font-bold font-mono tabular-nums">
            {masterBpm !== null ? formatBpm(masterBpm) : '---.-'}
          </span>
          <span className="text-[9px] text-muted-foreground">BPM</span>
        </div>

        {/* Beat indicator */}
        <div className="flex gap-1">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-sm transition-colors"
              style={{ width: 8, height: 8, background: i === 0 ? '#4ade80' : '#1f2937' }}
            />
          ))}
        </div>

        {/* Crossfader using shadcn Slider */}
        <div className="w-full flex flex-col gap-1">
          <div className="flex justify-between text-[9px] text-muted-foreground font-mono px-0.5">
            <span className="text-cyan-400">A</span>
            <span className="text-fuchsia-400">B</span>
          </div>
          <Slider
            min={0}
            max={100}
            value={[crossfader]}
            onValueChange={(v) => onCrossfaderChange(v[0])}
            className="w-full"
          />
          <div className="text-center text-[9px] text-muted-foreground font-mono tabular-nums">
            {crossfader === 50 ? 'C' : crossfader < 50 ? `A+${Math.round((50 - crossfader) * 2)}%` : `B+${Math.round((crossfader - 50) * 2)}%`}
          </div>
        </div>

        {/* Arrow faders */}
        <div className="flex gap-1.5 w-full">
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="flex-1 rounded py-0.5 text-xs bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center">
                <IconArrowLeft className="size-3 text-cyan-400" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Fade to A</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="flex-1 rounded py-0.5 text-xs bg-white/5 border border-white/10 hover:bg-white/10 flex items-center justify-center">
                <IconArrowRight className="size-3 text-fuchsia-400" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Fade to B</TooltipContent>
          </Tooltip>
        </div>

        {/* Sync B */}
        <button
          onClick={onToggleSync2}
          className={cn(
            'w-full rounded text-xs font-semibold py-1 border transition-colors mt-auto',
            sync2
              ? 'bg-fuchsia-500 text-black border-fuchsia-500'
              : 'border-fuchsia-500/30 text-fuchsia-400/50 hover:text-fuchsia-400 hover:border-fuchsia-500/60'
          )}
        >
          SYNC B
        </button>

      </CardContent>
    </Card>
  )
}

// ─── Library browser ───────────────────────────────────────────────────────

const PAGE_SIZE = 50

function LibraryBrowser({
  tracks,
  total,
  currentPage,
  currentSearch,
  activeDeck1Id,
  activeDeck2Id,
}: {
  tracks: TrackRow[]
  total: number
  currentPage: number
  currentSearch: string
  activeDeck1Id: number | null
  activeDeck2Id: number | null
}) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [searchInput, setSearchInput] = useState(currentSearch)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const buildParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString())
      for (const [k, v] of Object.entries(updates)) {
        if (v === undefined || v === '') params.delete(k)
        else params.set(k, v)
      }
      return params.toString()
    },
    [searchParams]
  )

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      router.push(`${pathname}?${buildParams({ search: searchInput || undefined, page: '1' })}`)
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput])

  const loadToDeck = (param: 'deck1' | 'deck2', id: number) => {
    router.push(`${pathname}?${buildParams({ [param]: String(id) })}`)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <Input
            placeholder="Search tracks..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-9 h-8 text-sm"
          />
        </div>
        <span className="text-xs text-muted-foreground">{total.toLocaleString()} tracks</span>
        <span className="text-xs text-muted-foreground ml-auto">
          Click <span className="text-cyan-400 font-semibold">A</span> or{' '}
          <span className="text-fuchsia-400 font-semibold">B</span> to load to deck
        </span>
      </div>

      {/* Table inside ScrollArea */}
      <ScrollArea className="h-[320px] rounded-lg border border-white/10">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-white/10 bg-[#0a0a0c]">
              {['#', 'Title / Artist', 'BPM', 'Key', 'Mood', 'LUFS', 'Duration', 'Load'].map((h) => (
                <th key={h} className="px-3 py-2 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tracks.map((track, idx) => {
              const onA = track.id === activeDeck1Id
              const onB = track.id === activeDeck2Id
              return (
                <tr
                  key={track.id}
                  className={cn(
                    'border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors',
                    onA && 'bg-cyan-500/[0.06]',
                    onB && 'bg-fuchsia-500/[0.06]'
                  )}
                >
                  <td className="px-3 py-1.5 text-xs text-muted-foreground tabular-nums w-8">
                    {(currentPage - 1) * PAGE_SIZE + idx + 1}
                  </td>
                  <td className="px-3 py-1.5 max-w-[260px]">
                    <div className="flex items-center gap-1.5">
                      {onA && <span className="text-[9px] font-bold text-cyan-400 bg-cyan-400/10 rounded px-1 shrink-0">A</span>}
                      {onB && <span className="text-[9px] font-bold text-fuchsia-400 bg-fuchsia-400/10 rounded px-1 shrink-0">B</span>}
                      <div className="min-w-0">
                        <div className="font-medium truncate">{track.title}</div>
                        {track.artists && (
                          <div className="text-xs text-muted-foreground truncate">{track.artists}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-center tabular-nums text-xs whitespace-nowrap">
                    {formatBpm(track.bpm)}
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    <span className="text-xs font-mono text-muted-foreground">{track.camelot ?? '—'}</span>
                  </td>
                  <td className="px-3 py-1.5">
                    <MoodBadge mood={track.mood} />
                  </td>
                  <td className="px-3 py-1.5 text-center text-xs tabular-nums text-muted-foreground whitespace-nowrap">
                    {track.integrated_lufs !== null ? track.integrated_lufs.toFixed(1) : '—'}
                  </td>
                  <td className="px-3 py-1.5 text-center text-xs tabular-nums text-muted-foreground whitespace-nowrap">
                    {track.duration_ms ? formatDuration(track.duration_ms) : '—'}
                  </td>
                  <td className="px-3 py-1.5">
                    <div className="flex gap-1 justify-center">
                      <button
                        onClick={() => loadToDeck('deck1', track.id)}
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-semibold border transition-colors',
                          onA
                            ? 'bg-cyan-500 text-black border-cyan-500'
                            : 'border-cyan-500/30 text-cyan-400/60 hover:bg-cyan-500/10 hover:text-cyan-400'
                        )}
                      >A</button>
                      <button
                        onClick={() => loadToDeck('deck2', track.id)}
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-semibold border transition-colors',
                          onB
                            ? 'bg-fuchsia-500 text-black border-fuchsia-500'
                            : 'border-fuchsia-500/30 text-fuchsia-400/60 hover:bg-fuchsia-500/10 hover:text-fuchsia-400'
                        )}
                      >B</button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {tracks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-sm text-muted-foreground italic">
                  No tracks found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </ScrollArea>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {total > 0
            ? `${(currentPage - 1) * PAGE_SIZE + 1}–${Math.min(currentPage * PAGE_SIZE, total)} of ${total.toLocaleString()}`
            : '0 tracks'}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={currentPage <= 1}
            onClick={() => router.push(`${pathname}?${buildParams({ page: String(currentPage - 1) })}`)}>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={currentPage >= totalPages}
            onClick={() => router.push(`${pathname}?${buildParams({ page: String(currentPage + 1) })}`)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Root ────────────────────────────────────────────────────────────────

interface DjPlayerProps {
  deck1: TrackDetail | null
  deck2: TrackDetail | null
  library: TrackRow[]
  libraryTotal: number
  currentPage: number
  currentSearch: string
}

export function DjPlayer({
  deck1, deck2, library, libraryTotal, currentPage, currentSearch,
}: DjPlayerProps) {
  const [playing1, setPlaying1] = useState(false)
  const [playing2, setPlaying2] = useState(false)
  const [crossfader, setCrossfader] = useState(50)
  const [sync1, setSync1] = useState(false)
  const [sync2, setSync2] = useState(false)

  return (
    <TooltipProvider>
      <div className="flex flex-1 flex-col gap-4 py-4 px-4 lg:px-6">

        {/* Player section */}
        <div className="grid gap-3" style={{ gridTemplateColumns: '1fr 148px 1fr' }}>
          <Deck side="A" track={deck1} isPlaying={playing1} onTogglePlay={() => setPlaying1((p) => !p)} />
          <Mixer
            deck1={deck1} deck2={deck2}
            crossfader={crossfader} onCrossfaderChange={setCrossfader}
            sync1={sync1} sync2={sync2}
            onToggleSync1={() => setSync1((s) => !s)}
            onToggleSync2={() => setSync2((s) => !s)}
          />
          <Deck side="B" track={deck2} isPlaying={playing2} onTogglePlay={() => setPlaying2((p) => !p)} />
        </div>

        {/* Library */}
        <Tabs defaultValue="library">
          <div className="flex items-center gap-3">
            <TabsList variant="line" className="h-8">
              <TabsTrigger value="library" className="text-xs">Library</TabsTrigger>
              <TabsTrigger value="loaded" className="text-xs">
                Loaded
                {(deck1 || deck2) && (
                  <Badge variant="secondary" className="ml-1 text-[9px] px-1 py-0 h-3.5">
                    {(deck1 ? 1 : 0) + (deck2 ? 1 : 0)}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <TabsContent value="library" className="mt-3">
            <LibraryBrowser
              tracks={library}
              total={libraryTotal}
              currentPage={currentPage}
              currentSearch={currentSearch}
              activeDeck1Id={deck1?.id ?? null}
              activeDeck2Id={deck2?.id ?? null}
            />
          </TabsContent>

          <TabsContent value="loaded" className="mt-3">
            <div className="grid grid-cols-2 gap-4">
              {[{ label: 'Deck A', track: deck1, color: '#22d3ee' }, { label: 'Deck B', track: deck2, color: '#e879f9' }].map(
                ({ label, track, color }) => (
                  <Card key={label} className="py-3 gap-2 border border-white/10 bg-[#0a0a0c]">
                    <CardContent className="px-3 flex flex-col gap-1.5">
                      <div className="text-xs font-semibold" style={{ color }}>{label}</div>
                      {track ? (
                        <>
                          <div className="font-medium text-sm truncate">{track.title}</div>
                          <div className="text-xs text-muted-foreground truncate">
                            {track.artists.map((a) => a.name).join(', ')}
                          </div>
                          <div className="flex gap-2 flex-wrap mt-1">
                            {track.features?.bpm !== null && track.features?.bpm !== undefined && (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                                {formatBpm(track.features.bpm)} BPM
                              </Badge>
                            )}
                            {track.features?.camelot && (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                                {track.features.camelot}
                              </Badge>
                            )}
                            {track.features?.mood && <MoodBadge mood={track.features.mood} />}
                            {track.features?.integrated_lufs !== null && track.features?.integrated_lufs !== undefined && (
                              <span className="text-[10px] text-muted-foreground font-mono">
                                {formatLufs(track.features.integrated_lufs)}
                              </span>
                            )}
                          </div>
                        </>
                      ) : (
                        <p className="text-xs text-muted-foreground italic">Empty</p>
                      )}
                    </CardContent>
                  </Card>
                )
              )}
            </div>
          </TabsContent>
        </Tabs>

      </div>
    </TooltipProvider>
  )
}
