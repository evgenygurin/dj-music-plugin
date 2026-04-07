import { PageShell, PageHeader } from '@/components/page-shell'
import { ToolActionCard } from '@/components/tool-action-card'
import { fetchToolSchema } from '@/lib/mcp-client'

export const dynamic = 'force-dynamic'

export default async function DeliveryPage() {
  const [deliverSchema, exportSchema] = await Promise.all([
    fetchToolSchema('deliver_set'),
    fetchToolSchema('export_set'),
  ])

  return (
    <PageShell title="Delivery">
      <PageHeader
        title="Delivery & Export"
        description="Score transitions, generate output files, and optionally push sets to Yandex Music."
      />

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
    </PageShell>
  )
}
