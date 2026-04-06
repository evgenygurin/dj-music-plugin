'use client'

import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
} from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { KeyCount } from '@/lib/queries/dashboard'

const chartConfig = {
  count: {
    label: 'Tracks',
    color: 'var(--chart-4)',
  },
} satisfies ChartConfig

export function CamelotWheelChart({ data }: { data: KeyCount[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[300px] w-full">
      <RadarChart data={data} margin={{ top: 8, right: 24, left: 24, bottom: 8 }}>
        <defs>
          <linearGradient id="camelotGradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--chart-4)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.15} />
          </linearGradient>
        </defs>
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis
          dataKey="camelot"
          tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Radar
          dataKey="count"
          fill="url(#camelotGradient)"
          stroke="var(--chart-4)"
          strokeWidth={2}
        />
      </RadarChart>
    </ChartContainer>
  )
}
