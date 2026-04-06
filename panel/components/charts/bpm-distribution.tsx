'use client'

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { BpmBin } from '@/lib/queries/dashboard'

const chartConfig = {
  count: {
    label: 'Tracks',
    color: 'var(--chart-1)',
  },
} satisfies ChartConfig

export function BpmDistributionChart({ data }: { data: BpmBin[] }) {
  return (
    <ChartContainer config={chartConfig} className="h-[220px] w-full">
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="bpmGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.9} />
            <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0.6} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="bin"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
          tickFormatter={(v) => `${v}`}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={32}
          tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
        />
        <ChartTooltip
          content={<ChartTooltipContent />}
          cursor={{ fill: 'var(--primary)', opacity: 0.08 }}
        />
        <Bar dataKey="count" fill="url(#bpmGradient)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  )
}
