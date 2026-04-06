const SECTION_TYPE_NAMES: Record<number, string> = {
  0: 'Intro',
  1: 'Attack',
  2: 'Build',
  3: 'Pre-Drop',
  4: 'Drop',
  5: 'Peak',
  6: 'Breakdown',
  7: 'Outro',
  8: 'Rise',
  9: 'Valley',
  10: 'Sustain',
  11: 'Unknown',
}

const SECTION_TYPE_COLORS: Record<number, string> = {
  0: '#64748b',
  1: '#3b82f6',
  2: '#6366f1',
  3: '#8b5cf6',
  4: '#ec4899',
  5: '#ef4444',
  6: '#f97316',
  7: '#94a3b8',
  8: '#06b6d4',
  9: '#10b981',
  10: '#84cc16',
  11: '#6b7280',
}

interface Section {
  section_type: number
  start_ms: number
  end_ms: number
  energy: number | null
  confidence: number | null
}

interface SectionsTimelineProps {
  sections: Section[]
}

function formatMs(ms: number): string {
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export function SectionsTimeline({ sections }: SectionsTimelineProps) {
  if (!sections || sections.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2 text-center">
        No sections detected.
      </div>
    )
  }

  const totalDuration = Math.max(...sections.map((s) => s.end_ms))

  return (
    <div className="space-y-2">
      <div className="flex h-8 w-full rounded overflow-hidden">
        {sections.map((section, i) => {
          const width = ((section.end_ms - section.start_ms) / totalDuration) * 100
          const color = SECTION_TYPE_COLORS[section.section_type] ?? '#6b7280'
          const name = SECTION_TYPE_NAMES[section.section_type] ?? 'Unknown'
          const title = `${name}\n${formatMs(section.start_ms)} – ${formatMs(section.end_ms)}${section.energy !== null ? `\nEnergy: ${section.energy.toFixed(3)}` : ''}`

          return (
            <div
              key={i}
              className="h-full flex-shrink-0 transition-opacity hover:opacity-80"
              style={{ width: `${width}%`, backgroundColor: color, minWidth: '2px' }}
              title={title}
            />
          )
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {sections.map((section, i) => {
          const color = SECTION_TYPE_COLORS[section.section_type] ?? '#6b7280'
          const name = SECTION_TYPE_NAMES[section.section_type] ?? 'Unknown'
          return (
            <div key={i} className="flex items-center gap-1 text-xs text-muted-foreground">
              <div className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              <span>{name}</span>
              <span className="font-mono">{formatMs(section.start_ms)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
