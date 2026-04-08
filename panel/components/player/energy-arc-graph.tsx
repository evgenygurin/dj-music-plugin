// panel/components/player/energy-arc-graph.tsx
'use client'

import {
  Area,
  AreaChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { SetTemplate, HistoryEntry } from '@/lib/set-narrative/types'

interface Props {
  template: SetTemplate
  elapsedSec: number
  history: HistoryEntry[]
}

export function EnergyArcGraph({ template, elapsedSec, history }: Props) {
  const totalSec = template.durationMin * 60

  // Predicted curve: one point per slot edge
  const predicted = template.slots.map((slot) => ({
    time: slot.position * totalSec,
    target: slot.energyLufs,
    slotMood: slot.targetMood,
  }))
  predicted.push({
    time: totalSec,
    target: template.slots[template.slots.length - 1].energyLufs,
    slotMood: null,
  })

  // Actual history played LUFS
  const actual = history
    .filter((h) => h.lufs != null)
    .map((h) => ({ time: h.playedAtSec, actual: h.lufs! }))

  const merged = [...predicted, ...actual].sort((a, b) => a.time - b.time)

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={merged}>
          <XAxis
            dataKey="time"
            type="number"
            domain={[0, totalSec]}
            tickFormatter={(v) => `${Math.floor(v / 60)}m`}
            stroke="currentColor"
            className="text-xs text-muted-foreground"
          />
          <YAxis
            domain={[-24, -2]}
            stroke="currentColor"
            className="text-xs text-muted-foreground"
          />
          <Tooltip
            labelFormatter={(v) => `${Math.floor(Number(v) / 60)}:${String(Math.floor(Number(v) % 60)).padStart(2, '0')}`}
            formatter={(v, k) => [`${Number(v).toFixed(1)} LUFS`, k]}
          />
          <Area
            type="monotone"
            dataKey="target"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.1}
            strokeDasharray="4 2"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="actual"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.3}
            isAnimationActive={false}
          />
          <ReferenceLine x={elapsedSec} stroke="var(--primary)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
