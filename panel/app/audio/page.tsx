import { PageShell, PageHeader } from '@/components/page-shell'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export const dynamic = 'force-dynamic'

export default async function AudioPage() {
  const [analyzeSchema, batchSchema, stemsSchema] = await Promise.all([
    fetchToolSchema('analyze_track'),
    fetchToolSchema('analyze_batch'),
    fetchToolSchema('separate_stems'),
  ])

  return (
    <PageShell title="Audio Analysis">
      <PageHeader
        title="Audio Analysis"
        description="Run BPM detection, key analysis, loudness measurement, and full audio pipeline on tracks."
      />

      <div className="grid gap-4 md:grid-cols-2">
        <ToolActionCard
          title="Analyze Track"
          description="Run audio analysis + mood classification on a single track. Detects BPM, key, loudness, energy, spectral features."
          toolName="analyze_track"
          schema={analyzeSchema ?? {}}
          buttonLabel="Analyze Track"
        />

        <ToolActionCard
          title="Batch Analysis"
          description="Analyze multiple tracks or an entire playlist. Supports parallel processing with configurable priority."
          toolName="analyze_batch"
          schema={batchSchema ?? {}}
          buttonLabel="Analyze Batch"
        />

        <ToolActionCard
          title="Separate Stems"
          description="Split a track into vocals, drums, bass, and other stems using ML model. Requires [stems] extra."
          toolName="separate_stems"
          schema={stemsSchema ?? {}}
          buttonLabel="Separate Stems"
        />
      </div>
    </PageShell>
  )
}
