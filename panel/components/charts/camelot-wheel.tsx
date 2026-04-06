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
    color: 'hsl(var(--chart-1))',
  },
} satisfies ChartConfig

export function CamelotWheelChart({ data }: { data: KeyCount[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[280px] w-full">
      <RadarChart data={data} margin={{ top: 8, right: 16, left: 16, bottom: 8 }}>
        <PolarGrid />
        <PolarAngleAxis dataKey="camelot" tick={{ fontSize: 10 }} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Radar
          dataKey="count"
          fill="var(--color-count)"
          fillOpacity={0.3}
          stroke="var(--color-count)"
        />
      </RadarChart>
    </ChartContainer>
  )
}
