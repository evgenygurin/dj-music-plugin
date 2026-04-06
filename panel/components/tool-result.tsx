'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { IconAlertCircle, IconCheck } from '@tabler/icons-react'
import type { ToolCallResult } from '@/lib/mcp-client'

function RenderValue({ value }: { value: unknown }): React.ReactNode {
  if (value === null || value === undefined)
    return <span className="text-muted-foreground">null</span>
  if (typeof value === 'boolean')
    return (
      <Badge variant={value ? 'default' : 'secondary'}>{String(value)}</Badge>
    )
  if (typeof value === 'number')
    return <span className="font-mono tabular-nums">{value}</span>
  if (typeof value === 'string') return <span>{value}</span>
  if (Array.isArray(value)) {
    if (value.length === 0)
      return <span className="text-muted-foreground">[]</span>
    if (typeof value[0] === 'object' && value[0] !== null) {
      const keys = Object.keys(value[0] as Record<string, unknown>)
      return (
        <div className="overflow-x-auto rounded border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                {keys.map((k) => (
                  <th key={k} className="px-3 py-2 text-left font-medium">
                    {k}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {value.map((row, i) => (
                <tr key={i} className="border-b last:border-0">
                  {keys.map((k) => (
                    <td key={k} className="px-3 py-2 font-mono text-xs">
                      {String(
                        (row as Record<string, unknown>)[k] ?? ''
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }
    return (
      <pre className="text-xs font-mono bg-muted/50 rounded p-2 overflow-auto">
        {JSON.stringify(value, null, 2)}
      </pre>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <div className="grid gap-2">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-start gap-2">
            <span className="text-sm font-medium text-muted-foreground min-w-[120px]">
              {k}:
            </span>
            <div className="flex-1">
              <RenderValue value={v} />
            </div>
          </div>
        ))}
      </div>
    )
  }
  return <span>{String(value)}</span>
}

export function ToolResult({ result }: { result: ToolCallResult }) {
  if (result.is_error) {
    const errorText =
      result.content.find((c) => c.text)?.text || 'Unknown error'
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <IconAlertCircle className="h-4 w-4 text-destructive" />
            <CardTitle className="text-sm font-medium text-destructive">
              Error
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <pre className="font-mono text-xs whitespace-pre-wrap text-destructive/80">
            {errorText}
          </pre>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <IconCheck className="h-4 w-4 text-green-500" />
          <CardTitle className="text-sm font-medium">
            {result.tool_name}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {result.structured_content ? (
          <RenderValue value={result.structured_content} />
        ) : result.content.length > 0 ? (
          <pre className="text-xs font-mono bg-muted/50 rounded p-3 overflow-auto whitespace-pre-wrap">
            {result.content.map((c) => c.text || '').join('\n')}
          </pre>
        ) : (
          <p className="text-sm text-muted-foreground">No content returned</p>
        )}
      </CardContent>
    </Card>
  )
}
