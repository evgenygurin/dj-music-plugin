'use client'

import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { SUBGENRE_COLORS, SUBGENRE_LABELS } from '@/lib/constants'
import type { MoodCount } from '@/lib/queries/dashboard'

const chartConfig = {
  count: {
    label: 'Tracks',
    color: 'hsl(var(--chart-1))',
  },
} satisfies ChartConfig

export function MoodDistributionChart({ data }: { data: MoodCount[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[320px] w-full">
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
      >
        <CartesianGrid horizontal={false} />
        <XAxis type="number" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis
          type="category"
          dataKey="mood"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={90}
          tickFormatter={(v: string) => SUBGENRE_LABELS[v] ?? v}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(label) => SUBGENRE_LABELS[String(label)] ?? String(label)}
            />
          }
        />
        <Bar dataKey="count" radius={[0, 2, 2, 0]}>
          {data.map((entry) => (
            <Cell
              key={entry.mood}
              fill={SUBGENRE_COLORS[entry.mood] ?? '#888'}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
