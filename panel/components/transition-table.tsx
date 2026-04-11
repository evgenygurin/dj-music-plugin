'use client'

import { IconPin } from '@tabler/icons-react'
import { MoodBadge } from '@/components/mood-badge'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { SetVersionTrack } from '@/lib/queries/sets'
import { formatBpm, scoreColor } from '@/lib/utils'

interface TransitionTableProps {
  tracks: SetVersionTrack[]
}

function ScoreBar({ score }: { score: number | null }) {
  if (score === null)
    return <span className="text-muted-foreground text-xs tabular-nums">—</span>

  const pct = Math.round(score * 100)
  const colorClass =
    score === 0
      ? 'bg-red-500'
      : score < 0.4
        ? 'bg-red-400'
        : score < 0.7
          ? 'bg-yellow-400'
          : 'bg-green-400'

  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden flex-shrink-0">
        <div
          className={`h-full rounded-full ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono text-xs tabular-nums ${scoreColor(score)}`}>
        {score.toFixed(2)}
      </span>
    </div>
  )
}

interface ScoreTooltipRowProps {
  label: string
  score: number | null
}

function ScoreTooltipRow({ label, score }: ScoreTooltipRowProps) {
  if (score === null) return null
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-background/70">{label}</span>
      <span className={`font-mono font-medium ${scoreColor(score)}`}>
        {score.toFixed(2)}
      </span>
    </div>
  )
}

export function TransitionTable({ tracks }: TransitionTableProps) {
  if (tracks.length === 0) {
    return <p className="text-sm text-muted-foreground">No tracks in this version.</p>
  }

  const getTransitionDelta = (index: number) => {
    const item = tracks[index]
    const t = item.track
    const tr = item.transition
    const isFirst = item.sort_index === 0
    const prevTrack = tracks[index - 1]?.track ?? null

    const bpmDelta =
      !isFirst && t.bpm !== null && prevTrack?.bpm !== null && prevTrack?.bpm !== undefined
        ? Math.abs(t.bpm - prevTrack.bpm)
        : null

    const keyDelta =
      !isFirst && tr?.harmonic_score !== null && tr?.harmonic_score !== undefined
        ? Math.round((1 - tr.harmonic_score) * 6)
        : null

    return { isFirst, bpmDelta, keyDelta }
  }

  return (
    <TooltipProvider delay={200}>
      <div>
        <div className="flex flex-col gap-2 md:hidden">
          {tracks.map((item, index) => {
            const t = item.track
            const tr = item.transition
            const { isFirst, bpmDelta, keyDelta } = getTransitionDelta(index)
            return (
              <div key={item.sort_index} className="rounded-xl border border-border/30 bg-card/70 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-sm font-medium">{t.title}</p>
                    <p className="line-clamp-1 text-xs text-muted-foreground">{t.artists || '—'}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant="outline" className="dj-data text-[10px]">
                      #{item.sort_index + 1}
                    </Badge>
                    {item.pinned ? <IconPin className="size-3 text-foreground/70" /> : null}
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Badge variant="secondary" className="dj-data text-[10px]">
                    {formatBpm(t.bpm)} BPM
                  </Badge>
                  <Badge variant="outline" className="dj-data text-[10px]">
                    {t.camelot ?? '—'}
                  </Badge>
                  <MoodBadge mood={t.mood} />
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  <div className="rounded-lg border border-border/30 bg-card/70 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Score</p>
                    <p className={`dj-data text-xs ${scoreColor(tr?.overall_quality ?? null)}`}>
                      {tr?.overall_quality !== null && tr?.overall_quality !== undefined ? tr.overall_quality.toFixed(2) : '—'}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border/30 bg-card/70 p-1.5">
                    <p className="text-[10px] text-muted-foreground">BPM Δ</p>
                    <p className="dj-data text-xs">{isFirst ? '—' : bpmDelta !== null ? `±${bpmDelta.toFixed(1)}` : '—'}</p>
                  </div>
                  <div className="rounded-lg border border-border/30 bg-card/70 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Key Δ</p>
                    <p className="dj-data text-xs">{isFirst ? '—' : keyDelta !== null ? keyDelta : '—'}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="hidden rounded-md border md:block">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>Track</TableHead>
                <TableHead className="w-16">BPM</TableHead>
                <TableHead className="w-14">Key</TableHead>
                <TableHead className="w-28">Mood</TableHead>
                <TableHead className="w-36">Score</TableHead>
                <TableHead className="w-16">BPM Δ</TableHead>
                <TableHead className="w-12">Key Δ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tracks.map((item, index) => {
                const t = item.track
                const tr = item.transition
                const { isFirst, bpmDelta, keyDelta } = getTransitionDelta(index)

                const hasComponents =
                  tr &&
                  (tr.bpm_score !== null ||
                    tr.harmonic_score !== null ||
                    tr.energy_score !== null ||
                    tr.spectral_score !== null ||
                    tr.groove_score !== null)

                return (
                  <TableRow key={item.sort_index}>
                    <TableCell className="text-muted-foreground text-xs tabular-nums">
                      <div className="flex items-center gap-1">
                        {item.sort_index + 1}
                        {item.pinned ? (
                          <IconPin className="h-3 w-3 flex-shrink-0 text-foreground/60" />
                        ) : null}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="min-w-0">
                        <div className="max-w-[200px] truncate text-sm font-medium">
                          {t.title}
                        </div>
                        {t.artists ? (
                          <div className="max-w-[200px] truncate text-xs text-muted-foreground">
                            {t.artists}
                          </div>
                        ) : null}
                      </div>
                    </TableCell>

                    <TableCell>
                      <span className="font-mono text-xs tabular-nums">{formatBpm(t.bpm)}</span>
                    </TableCell>

                    <TableCell>
                      <span className="font-mono text-xs">{t.camelot ?? '—'}</span>
                    </TableCell>

                    <TableCell>
                      <MoodBadge mood={t.mood} />
                    </TableCell>

                    <TableCell>
                      {isFirst ? (
                        <span className="text-muted-foreground text-xs">—</span>
                      ) : hasComponents ? (
                        <Tooltip>
                          <TooltipTrigger
                            render={<button type="button" className="cursor-default" />}
                          >
                            <ScoreBar score={tr?.overall_quality ?? null} />
                          </TooltipTrigger>
                          <TooltipContent side="left" className="min-w-[140px]">
                            <div className="flex flex-col gap-1 py-0.5">
                              <ScoreTooltipRow label="BPM" score={tr?.bpm_score ?? null} />
                              <ScoreTooltipRow label="Harmonic" score={tr?.harmonic_score ?? null} />
                              <ScoreTooltipRow label="Energy" score={tr?.energy_score ?? null} />
                              <ScoreTooltipRow label="Spectral" score={tr?.spectral_score ?? null} />
                              <ScoreTooltipRow label="Groove" score={tr?.groove_score ?? null} />
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <ScoreBar score={tr?.overall_quality ?? null} />
                      )}
                    </TableCell>

                    <TableCell>
                      {isFirst ? (
                        <span className="text-muted-foreground text-xs">—</span>
                      ) : (
                        <span
                          className={`font-mono text-xs tabular-nums ${
                            bpmDelta === null
                              ? 'text-muted-foreground'
                              : bpmDelta > 6
                                ? 'text-red-400'
                                : bpmDelta > 3
                                  ? 'text-yellow-400'
                                  : 'text-green-400'
                          }`}
                        >
                          {bpmDelta === null ? '—' : `±${bpmDelta.toFixed(1)}`}
                        </span>
                      )}
                    </TableCell>

                    <TableCell>
                      {isFirst ? (
                        <span className="text-muted-foreground text-xs">—</span>
                      ) : (
                        <span
                          className={`font-mono text-xs tabular-nums ${
                            keyDelta === null
                              ? 'text-muted-foreground'
                              : keyDelta >= 4
                                ? 'text-red-400'
                                : keyDelta >= 2
                                  ? 'text-yellow-400'
                                  : 'text-green-400'
                          }`}
                        >
                          {keyDelta === null ? '—' : keyDelta}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      </div>
    </TooltipProvider>
  )
}
