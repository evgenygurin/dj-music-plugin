'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { SUBGENRE_LABELS } from '@/lib/constants'
import type { MoodCount } from '@/lib/queries/dashboard'

const chartConfig = {
  count: {
    label: 'Tracks',
    color: 'hsl(var(--foreground) / 0.35)',
  },
} satisfies ChartConfig

export function MoodDistributionChart({ data }: { data: MoodCount[] }) {
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
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
        >
          <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeOpacity={0.5} />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
          />
          <YAxis
            type="category"
            dataKey="mood"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={104}
            tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
            tickFormatter={(v: string) => SUBGENRE_LABELS[v] ?? v}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(label) => SUBGENRE_LABELS[String(label)] ?? String(label)}
              />
            }
            cursor={{ fill: 'hsl(var(--muted))' }}
          />
          <Bar
            dataKey="count"
            fill="hsl(var(--foreground) / 0.35)"
            radius={[0, 3, 3, 0]}
            barSize={18}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
