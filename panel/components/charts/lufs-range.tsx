'use client'

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import {
  chartGridStroke,
  chartLineStroke,
  chartTickColor,
  monoChartConfig,
} from '@/lib/chart-theme'
import type { LufsBin } from '@/lib/queries/dashboard'

export function LufsRangeChart({ data }: { data: LufsBin[] }) {
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
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="lufsGradientMono" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={chartLineStroke} stopOpacity={0.3} />
              <stop offset="95%" stopColor={chartLineStroke} stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={chartGridStroke} strokeOpacity={0.5} />
          <XAxis
            dataKey="lufs"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: chartTickColor }}
            tickFormatter={(v) => `${v}`}
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
            cursor={{ stroke: chartGridStroke }}
          />
          <Area
            type="monotone"
            dataKey="count"
            fill="url(#lufsGradientMono)"
            stroke={chartLineStroke}
            strokeOpacity={0.82}
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
