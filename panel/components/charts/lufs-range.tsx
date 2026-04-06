'use client'

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { LufsBin } from '@/lib/queries/dashboard'

const chartConfig = {
  count: {
    label: 'Tracks',
    color: 'hsl(var(--foreground) / 0.35)',
  },
} satisfies ChartConfig

export function LufsRangeChart({ data }: { data: LufsBin[] }) {
  if (data.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
        No data
      </div>
    )
  }

  return (
    <ChartContainer config={chartConfig} className="min-h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <defs>
            <linearGradient id="lufsGradientMono" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(var(--foreground))" stopOpacity={0.2} />
              <stop offset="95%" stopColor="hsl(var(--foreground))" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeOpacity={0.5} />
          <XAxis
            dataKey="lufs"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickFormatter={(v) => `${v}`}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={32}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
          />
          <ChartTooltip
            content={<ChartTooltipContent hideLabel={false} />}
            cursor={{ stroke: 'hsl(var(--border))' }}
          />
          <Area
            type="monotone"
            dataKey="count"
            fill="url(#lufsGradientMono)"
            stroke="hsl(var(--foreground) / 0.5)"
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
