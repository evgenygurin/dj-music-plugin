'use client'

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'

export interface EnergyArcData {
  position: number
  title: string
  lufs: number
  fill: string
}

const chartConfig = {
  lufs: {
    label: 'LUFS',
  },
} satisfies ChartConfig

const LUFS_MIN = -20
const LUFS_MAX = -4

function energyColor(lufs: number): string {
  const normalized = Math.max(0, Math.min(1, (lufs - LUFS_MIN) / (LUFS_MAX - LUFS_MIN)))
  if (normalized < 0.4) return '#22c55e'
  if (normalized < 0.7) return '#eab308'
  return '#ef4444'
}

export function prepareEnergyArcData(
  data: Array<{ position: number; title: string; lufs: number }>
): EnergyArcData[] {
  return data.map((d) => ({ ...d, fill: energyColor(d.lufs) }))
}

export function EnergyArcChart({ data }: { data: EnergyArcData[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[200px] w-full">
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="position"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v) => `#${v}`}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={40}
          domain={[LUFS_MIN - 2, LUFS_MAX + 2]}
        />
        <ChartTooltip content={<ChartTooltipContent nameKey="title" />} />
        <Bar dataKey="lufs" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ChartContainer>
  )
}
