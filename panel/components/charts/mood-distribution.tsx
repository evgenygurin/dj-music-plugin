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
    color: 'var(--chart-1)',
  },
} satisfies ChartConfig

export function MoodDistributionChart({ data }: { data: MoodCount[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[340px] w-full">
      <BarChart
        layout="vertical"
        data={data}
        margin={{ top: 4, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
        />
        <YAxis
          type="category"
          dataKey="mood"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={100}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          tickFormatter={(v: string) => SUBGENRE_LABELS[v] ?? v}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(label) => SUBGENRE_LABELS[String(label)] ?? String(label)}
            />
          }
          cursor={{ fill: 'var(--primary)', opacity: 0.06 }}
        />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
          {data.map((entry) => (
            <Cell
              key={entry.mood}
              fill={SUBGENRE_COLORS[entry.mood] ?? 'var(--chart-1)'}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}
