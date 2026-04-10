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
import { SUBGENRE_LABELS } from '@/lib/constants'
import type { MoodCount } from '@/lib/queries/dashboard'

export function MoodDistributionChart({ data }: { data: MoodCount[] }) {
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
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
        >
          <CartesianGrid horizontal={false} stroke={chartGridStroke} strokeOpacity={0.5} />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: chartTickColor }}
          />
          <YAxis
            type="category"
            dataKey="mood"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            width={104}
            tick={{ fontSize: 11, fill: chartTickColor }}
            tickFormatter={(v: string) => SUBGENRE_LABELS[v] ?? v}
          />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(label) => SUBGENRE_LABELS[String(label)] ?? String(label)}
              />
            }
            cursor={{ fill: chartCursorFill }}
          />
          <Bar dataKey="count" fill={chartBarFill} fillOpacity={0.72} radius={[0, 3, 3, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}
