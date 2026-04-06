import { SiteHeader } from '@/components/site-header'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export default async function CurationPage() {
  const [classifySchema, auditSchema, distributeSchema, syncSchema, pushSchema, libraryStatsSchema] =
    await Promise.all([
      fetchToolSchema('classify_mood'),
      fetchToolSchema('audit_playlist'),
      fetchToolSchema('distribute_to_subgenres'),
      fetchToolSchema('sync_playlist'),
      fetchToolSchema('push_set_to_ym'),
      fetchToolSchema('get_library_stats'),
    ])

  return (
    <>
      <SiteHeader title="Curation" />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6">
        <div>
          <h1 className="text-lg font-semibold">Curation</h1>
          <p className="text-sm text-muted-foreground">
            Classify tracks by subgenre, distribute to playlists, and sync with Yandex Music.
          </p>
        </div>

        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            Classification
          </h2>
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

        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            Distribution
          </h2>
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

        <div>
          <h2 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            Sync & Push
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <ToolActionCard
              title="Sync Playlist"
              description="Bidirectional sync between local playlist and Yandex Music. Push local changes or pull remote updates."
              toolName="sync_playlist"
              schema={syncSchema ?? {}}
              buttonLabel="Sync Playlist"
            />

            <ToolActionCard
              title="Push Set to YM"
              description="Push a DJ set as a Yandex Music playlist. Creates or updates the playlist with set track order."
              toolName="push_set_to_ym"
              schema={pushSchema ?? {}}
              buttonLabel="Push to YM"
            />
          </div>
        </div>
      </div>
    </>
  )
}
