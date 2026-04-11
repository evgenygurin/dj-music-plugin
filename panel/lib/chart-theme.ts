import type { ChartConfig } from '@/components/ui/chart'

export const monoChartConfig = {
  count: {
    label: 'Tracks',
    color: 'var(--chart-1)',
  },
} satisfies ChartConfig

export const chartGridStroke = 'var(--border)'
export const chartTickColor = 'var(--muted-foreground)'
export const chartCursorFill = 'var(--muted)'
export const chartBarFill = 'var(--chart-1)'
export const chartLineStroke = 'var(--chart-1)'
