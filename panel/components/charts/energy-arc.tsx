'use client'

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'

import type { EnergyArcData } from './energy-arc-data'

// Re-export for existing imports. New server-side callers should import
// `prepareEnergyArcData` and `EnergyArcData` directly from
// './energy-arc-data' to avoid pulling the client boundary.
export { prepareEnergyArcData, type EnergyArcData } from './energy-arc-data'

const chartConfig = {
  lufs: {
    label: 'LUFS',
  },
} satisfies ChartConfig

const LUFS_MIN = -20
const LUFS_MAX = -4

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
