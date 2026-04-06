import { SiteHeader } from '@/components/site-header'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export default async function DeliveryPage() {
  const [deliverSchema, exportSchema] = await Promise.all([
    fetchToolSchema('deliver_set'),
    fetchToolSchema('export_set'),
  ])

  return (
    <>
      <SiteHeader title="Delivery" />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6">
        <div>
          <h1 className="text-lg font-semibold">Delivery & Export</h1>
          <p className="text-sm text-muted-foreground">
            Score transitions, generate output files, and optionally push sets to Yandex Music.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <ToolActionCard
            title="Deliver Set"
            description="Full delivery pipeline: score transitions, copy MP3s, write M3U8/JSON/cheat sheet, optional YM sync."
            toolName="deliver_set"
            schema={deliverSchema ?? {}}
            buttonLabel="Deliver Set"
          />

          <ToolActionCard
            title="Export Set"
            description="Export a set in a specific format: M3U8 playlist, JSON guide, or Rekordbox XML."
            toolName="export_set"
            schema={exportSchema ?? {}}
            buttonLabel="Export Set"
          />
        </div>
      </div>
    </>
  )
}
