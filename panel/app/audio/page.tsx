import { SiteHeader } from '@/components/site-header'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export default async function AudioPage() {
  const [analyzeSchema, batchSchema, stemsSchema] = await Promise.all([
    fetchToolSchema('analyze_track'),
    fetchToolSchema('analyze_batch'),
    fetchToolSchema('separate_stems'),
  ])

  return (
    <>
      <SiteHeader title="Audio Analysis" />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6">
        <div>
          <h1 className="text-lg font-semibold">Audio Analysis</h1>
          <p className="text-sm text-muted-foreground">
            Run BPM detection, key analysis, loudness measurement, and full audio pipeline on tracks.
          </p>
        </div>

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
      </div>
    </>
  )
}
