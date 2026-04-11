import { fetchTools, type ToolInfo } from '@/lib/mcp-client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageShell, PageHeader } from '@/components/page-shell'
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from '@/components/ui/empty'
import { IconTool } from '@tabler/icons-react'
import Link from 'next/link'

export const dynamic = 'force-dynamic'

const TAG_ORDER = [
  'core',
  'sets',
  'delivery',
  'discovery',
  'curation',
  'sync',
  'ym',
  'audio',
  'atomic',
  'admin',
]

export default async function ToolsPage() {
  const tools = await fetchTools()

  const grouped = tools.reduce<Record<string, ToolInfo[]>>((acc, tool) => {
    const tag = tool.tags[0] || 'other'
    if (!acc[tag]) acc[tag] = []
    acc[tag].push(tool)
    return acc
  }, {})

  const sortedTags = [
    ...TAG_ORDER.filter((t) => grouped[t]),
    ...Object.keys(grouped).filter((t) => !TAG_ORDER.includes(t)),
  ]

  return (
    <PageShell title="Tools">
      <PageHeader
        title="MCP Tools"
        description={`${tools.length} tools available`}
      />

      {tools.length === 0 ? (
        <Empty className="border min-h-[200px]">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <IconTool />
            </EmptyMedia>
            <EmptyTitle>No tools available</EmptyTitle>
            <EmptyDescription>
              Is the MCP backend running on port 8000?
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        sortedTags.map((tag) => (
          <div key={tag} className="grid gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-[10px] uppercase tracking-wider text-muted-foreground/50 capitalize">{tag}</h2>
              <span className="dj-data text-muted-foreground/50">
                {grouped[tag].length}
              </span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {grouped[tag].map((tool) => (
                <Link key={tool.name} href={`/tools/${tool.name}`}>
                  <Card className="shadow-none border-border/20 bg-card/50 hover:bg-accent/50 transition-colors cursor-pointer h-full">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-mono text-foreground">{tool.name}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {tool.description || 'No description'}
                      </p>
                      <div className="flex gap-1 mt-2">
                        {tool.annotations?.readOnlyHint === true && (
                          <Badge variant="outline" className="text-[10px]">
                            read-only
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        ))
      )}
    </PageShell>
  )
}
