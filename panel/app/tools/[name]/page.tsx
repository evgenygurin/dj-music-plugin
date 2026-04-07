import { fetchTools, fetchToolSchema } from '@/lib/mcp-client'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell, PageHeader } from '@/components/page-shell'
import { notFound } from 'next/navigation'
import { ToolRunner } from './tool-runner'

export const dynamic = 'force-dynamic'

export default async function ToolPage({
  params,
}: {
  params: Promise<{ name: string }>
}) {
  const { name } = await params
  const tools = await fetchTools()
  const tool = tools.find((t) => t.name === name)

  if (!tool) notFound()

  const schema = await fetchToolSchema(name)

  return (
    <PageShell
      title={tool.name}
      parent={{ label: 'Tools', href: '/tools' }}
      className="max-w-3xl"
    >
      <PageHeader
        title={tool.name}
        titleClassName="font-mono text-xl"
        description={
          <>
            {tool.description || 'No description'}
            {tool.timeout ? (
              <span className="ml-2 text-xs">(timeout: {tool.timeout}s)</span>
            ) : null}
          </>
        }
        badge={
          <div className="flex items-center gap-1">
            {tool.tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
            {tool.annotations?.readOnlyHint === true && (
              <Badge variant="outline" className="text-xs">
                read-only
              </Badge>
            )}
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <ToolRunner
            toolName={name}
            schema={schema || { type: 'object', properties: {} }}
          />
        </CardContent>
      </Card>
    </PageShell>
  )
}
