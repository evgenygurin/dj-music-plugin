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
import type { KeyCount } from '@/lib/queries/dashboard'

// Sort by Camelot label: 1A, 1B, 2A, 2B, ..., 12A, 12B
function sortByCamelot(data: KeyCount[]): KeyCount[] {
  return [...data].sort((a, b) => {
    const parseKey = (k: string) => {
      const num = parseInt(k, 10)
      const mode = k.endsWith('B') ? 1 : 0
      return num * 2 + mode
    }
    return parseKey(a.camelot) - parseKey(b.camelot)
  })
}

export function CamelotWheelChart({ data }: { data: KeyCount[] }) {
  if (data.length === 0) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-muted-foreground">
        No data
      </div>
    )
  }

  const sorted = sortByCamelot(data)

  return (
    <ChartContainer config={monoChartConfig} className="min-h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={chartGridStroke} strokeOpacity={0.5} />
          <XAxis
            dataKey="camelot"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 10, fill: chartTickColor }}
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
