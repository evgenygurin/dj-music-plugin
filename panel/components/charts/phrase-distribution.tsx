'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  chartBarFill,
  chartCursorFill,
  chartGridStroke,
  chartTickColor,
  monoChartConfig,
} from '@/lib/chart-theme'
import type { PhraseCount } from '@/lib/queries/dashboard'

export function PhraseDistributionChart({ data }: { data: PhraseCount[] }) {
  if (data.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
        No data
      </div>
    )
  }

  return (
    <ChartContainer config={monoChartConfig} className="min-h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={chartGridStroke} strokeOpacity={0.5} />
          <XAxis
            dataKey="bars"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: chartTickColor }}
            tickFormatter={(v) => `${v}b`}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={32}
            tick={{ fontSize: 11, fill: chartTickColor }}
          />
          <ChartTooltip
            content={<ChartTooltipContent hideLabel={false} />}
            cursor={{ fill: chartCursorFill }}
          />
          <Bar dataKey="count" fill={chartBarFill} fillOpacity={0.72} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
