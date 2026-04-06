'use client'

import { IconPin } from '@tabler/icons-react'
import { MoodBadge } from '@/components/mood-badge'
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

  return (
    <TooltipProvider delay={200}>
      <div className="rounded-md border">
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
            {tracks.map((item) => {
              const t = item.track
              const tr = item.transition
              const isFirst = item.sort_index === 0

              // Compute BPM delta with previous track
              const prevTrack = tracks[item.sort_index - 1]?.track ?? null
              const bpmDelta =
                !isFirst && t.bpm !== null && prevTrack?.bpm !== null && prevTrack?.bpm !== undefined
                  ? Math.abs(t.bpm - prevTrack.bpm)
                  : null

              // Key distance: approximate from harmonic score (0=close, 6=far)
              const keyDelta =
                !isFirst && tr?.harmonic_score !== null && tr?.harmonic_score !== undefined
                  ? Math.round((1 - tr.harmonic_score) * 6)
                  : null

              const hasComponents =
                tr &&
                (tr.bpm_score !== null ||
                  tr.harmonic_score !== null ||
                  tr.energy_score !== null ||
                  tr.spectral_score !== null ||
                  tr.groove_score !== null)

              return (
                <TableRow key={item.sort_index}>
                  {/* # */}
                  <TableCell className="text-muted-foreground text-xs tabular-nums">
                    <div className="flex items-center gap-1">
                      {item.sort_index + 1}
                      {item.pinned && (
                        <IconPin className="h-3 w-3 text-amber-400 flex-shrink-0" />
                      )}
                    </div>
                  </TableCell>

                  {/* Track */}
                  <TableCell>
                    <div className="min-w-0">
                      <div className="truncate font-medium text-sm max-w-[200px]">
                        {t.title}
                      </div>
                      {t.artists && (
                        <div className="truncate text-xs text-muted-foreground max-w-[200px]">
                          {t.artists}
                        </div>
                      )}
                    </div>
                  </TableCell>

                  {/* BPM */}
                  <TableCell>
                    <span className="font-mono text-xs tabular-nums">{formatBpm(t.bpm)}</span>
                  </TableCell>

                  {/* Key */}
                  <TableCell>
                    <span className="font-mono text-xs">{t.camelot ?? '—'}</span>
                  </TableCell>

                  {/* Mood */}
                  <TableCell>
                    <MoodBadge mood={t.mood} />
                  </TableCell>

                  {/* Score (with tooltip for components) */}
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

                  {/* BPM delta */}
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

                  {/* Key delta */}
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
    </TooltipProvider>
  )
}
