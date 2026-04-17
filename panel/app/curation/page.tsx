import { PageShell, PageHeader } from '@/components/page-shell'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export const dynamic = 'force-dynamic'

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[10px] uppercase tracking-wider text-muted-foreground/50">
      {children}
    </h2>
  )
}

export default async function CurationPage() {
  const [classifySchema, auditSchema, distributeSchema, syncSchema, pushSchema, libraryStatsSchema] =
    await Promise.all([
      fetchToolSchema('classify_mood'),
      fetchToolSchema('audit_playlist'),
      fetchToolSchema('distribute_to_subgenres'),
      fetchToolSchema('sync_playlist'),
      fetchToolSchema('push_set_to_platform'),
      fetchToolSchema('get_library_stats'),
    ])

  return (
    <PageShell title="Curation">
      <PageHeader
        title="Curation"
        description="Classify tracks by subgenre, distribute to playlists, and sync with platform."
      />

      <div className="flex flex-col gap-3">
        <SectionTitle>Classification</SectionTitle>
        <div className="grid gap-4 md:grid-cols-2">
          <ToolActionCard
            title="Classify Mood"
            description="Classify tracks by 15 techno subgenres using audio features. Optionally reclassify already-classified tracks."
            toolName="classify_mood"
            schema={classifySchema ?? {}}
            buttonLabel="Classify Mood"
          />

          <ToolActionCard
            title="Audit Playlist"
            description="Check playlist tracks against techno quality criteria (BPM range, energy, kick, spectral). Identify non-conforming tracks."
            toolName="audit_playlist"
            schema={auditSchema ?? {}}
            buttonLabel="Audit Playlist"
          />

          <ToolActionCard
            title="Library Stats"
            description="Get overall library statistics: track count, feature coverage, subgenre distribution."
            toolName="get_library_stats"
            schema={libraryStatsSchema ?? {}}
            buttonLabel="Get Stats"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <SectionTitle>Distribution</SectionTitle>
        <div className="grid gap-4 md:grid-cols-2">
          <ToolActionCard
            title="Distribute to Subgenres"
            description="Send classified tracks to their respective subgenre playlists. Supports dry run to preview changes."
            toolName="distribute_to_subgenres"
            schema={distributeSchema ?? {}}
            buttonLabel="Distribute"
          />
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <SectionTitle>Sync &amp; Push</SectionTitle>
        <div className="grid gap-4 md:grid-cols-2">
          <ToolActionCard
            title="Sync Playlist"
            description="Bidirectional sync between local playlist and platform. Push local changes or pull remote updates."
            toolName="sync_playlist"
            schema={syncSchema ?? {}}
            buttonLabel="Sync Playlist"
          />

          <ToolActionCard
            title="Push Set to Platform"
            description="Push a DJ set as a platform playlist. Creates or updates the playlist with set track order."
            toolName="push_set_to_platform"
            schema={pushSchema ?? {}}
            buttonLabel="Push to Platform"
          />
        </div>
      </div>
    </PageShell>
  )
}
