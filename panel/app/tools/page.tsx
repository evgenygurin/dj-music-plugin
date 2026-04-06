import { fetchTools, type ToolInfo } from '@/lib/mcp-client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SiteHeader } from '@/components/site-header'
import Link from 'next/link'

export const revalidate = 60

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
    <>
      <SiteHeader title="Tools" />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6">
        <div>
          <h1 className="text-lg font-semibold">MCP Tools</h1>
          <p className="text-sm text-muted-foreground">
            {tools.length} tools available
          </p>
        </div>

        {sortedTags.map((tag) => (
          <div key={tag} className="grid gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-medium capitalize">{tag}</h2>
              <Badge variant="secondary" className="text-xs">
                {grouped[tag].length}
              </Badge>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {grouped[tag].map((tool) => (
                <Link key={tool.name} href={`/tools/${tool.name}`}>
                  <Card className="hover:bg-accent/50 transition-colors cursor-pointer h-full">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-mono">
                        {tool.name}
                      </CardTitle>
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
        ))}

        {tools.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center py-20">
            <p className="text-sm text-muted-foreground">
              No tools available. Is the MCP backend running?
            </p>
          </div>
        )}
      </div>
    </>
  )
}
