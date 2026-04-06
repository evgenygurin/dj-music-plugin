import { fetchTools, fetchToolSchema } from '@/lib/mcp-client'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SiteHeader } from '@/components/site-header'
import { notFound } from 'next/navigation'
import { ToolRunner } from './tool-runner'

export const revalidate = 60

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
    <>
      <SiteHeader title={tool.name} parent={{ label: 'Tools', href: '/tools' }} />
      <div className="flex flex-1 flex-col gap-6 py-6 px-4 lg:px-6 max-w-2xl">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-lg font-semibold font-mono">{tool.name}</h1>
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
          <p className="text-sm text-muted-foreground">
            {tool.description || 'No description'}
          </p>
          {tool.timeout && (
            <p className="text-xs text-muted-foreground mt-1">
              Timeout: {tool.timeout}s
            </p>
          )}
        </div>

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
      </div>
    </>
  )
}
