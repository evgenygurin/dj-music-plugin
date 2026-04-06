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
import type { SetVersionTrack } from '@/lib/queries/sets'
import { formatBpm, formatLufs, scoreColor } from '@/lib/utils'

interface TransitionTableProps {
  tracks: SetVersionTrack[]
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-xs">—</span>
  return (
    <span className={`font-mono text-xs tabular-nums ${scoreColor(score)}`}>
      {score.toFixed(2)}
    </span>
  )
}

export function TransitionTable({ tracks }: TransitionTableProps) {
  if (tracks.length === 0) {
    return <p className="text-sm text-muted-foreground">No tracks in this version.</p>
  }

  return (
    <div className="rounded-md border overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">#</TableHead>
            <TableHead>Track</TableHead>
            <TableHead className="w-16">BPM</TableHead>
            <TableHead className="w-14">Key</TableHead>
            <TableHead className="w-28">Mood</TableHead>
            <TableHead className="w-20">LUFS</TableHead>
            <TableHead className="w-14">Overall</TableHead>
            <TableHead className="w-12">Bpm</TableHead>
            <TableHead className="w-12">Harm</TableHead>
            <TableHead className="w-12">Nrg</TableHead>
            <TableHead className="w-12">Spec</TableHead>
            <TableHead className="w-12">Grv</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tracks.map((item) => {
            const t = item.track
            const tr = item.transition
            const isFirst = item.sort_index === 0

            return (
              <TableRow key={item.sort_index}>
                <TableCell className="text-muted-foreground text-xs tabular-nums">
                  <div className="flex items-center gap-1">
                    {item.sort_index + 1}
                    {item.pinned && (
                      <IconPin className="h-3 w-3 text-amber-400 flex-shrink-0" />
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="max-w-[200px]">
                    <div className="truncate font-medium text-sm">{t.title}</div>
                    {t.artists && (
                      <div className="truncate text-xs text-muted-foreground">{t.artists}</div>
                    )}
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
                  <span className="font-mono text-xs tabular-nums">
                    {formatLufs(t.integrated_lufs)}
                  </span>
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.overall_quality ?? null} />
                  )}
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.bpm_score ?? null} />
                  )}
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.harmonic_score ?? null} />
                  )}
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.energy_score ?? null} />
                  )}
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.spectral_score ?? null} />
                  )}
                </TableCell>
                <TableCell>
                  {isFirst ? (
                    <span className="text-muted-foreground text-xs">—</span>
                  ) : (
                    <ScoreCell score={tr?.groove_score ?? null} />
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
